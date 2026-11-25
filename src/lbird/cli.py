from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lbird.collectors.catalog_collector import load_catalog, load_yaml_file, make_slug
from lbird.collectors.github_discovery_collector import discover_github_directories
from lbird.collectors.news_collector import collect_news
from lbird.collectors.official_resolver import resolve_missing_official_urls
from lbird.collectors.risk_feed_collector import collect_risk_feeds
from lbird.collectors.sub_probe_collector import load_secret_subscriptions, probe_subscription
from lbird.collectors.telegram_collector import fetch_telegram_channel
from lbird.collectors.web_health_collector import probe_website
from lbird.exporter import export_all, load_json_or, update_readme_dashboard, validate_data_dir
from lbird.http_client import PoliteHttpClient
from lbird.models import SubProbeResult, TelegramResult, WebHealthResult
from lbird.scoring import build_monthly_report, evaluate_target


async def run_pipeline(config_dir: Path, data_dir: Path, readme_path: Path | None, offline: bool = False) -> dict[str, Any]:
    sources_cfg = load_yaml_file(config_dir / "sources.yaml")
    http_cfg = sources_cfg.get("http") or {}
    probe_cfg = sources_cfg.get("probe") or {}
    discovery_cfg = sources_cfg.get("github_discovery") or {}
    max_targets = int(discovery_cfg.get("max_total_targets") or 200)
    ua = str(sources_cfg.get("user_agent") or "LBird-Research-Bot/1.0")

    state = load_json_or(data_dir / "state.json", {"targets": {}})
    if not isinstance(state, dict) or not isinstance(state.get("targets"), dict):
        state = {"targets": {}}

    secret_subs = load_secret_subscriptions()
    now = datetime.now(timezone.utc)

    async with PoliteHttpClient(
        user_agent=ua,
        timeout_sec=float(http_cfg.get("timeout_sec", 8.0)),
        per_domain_delay_sec=float(http_cfg.get("per_domain_delay_sec", 0.3)),
        respect_robots_txt=bool(http_cfg.get("respect_robots_txt", True)),
    ) as client:
        (catalog, catalog_deals), news_list, (risk_map, risk_entries), discovered = await asyncio.gather(
            load_catalog(config_dir, sources_cfg, None if offline else client),
            asyncio.sleep(0, result=[]) if offline else collect_news(sources_cfg.get("news_feeds") or [], client),
            asyncio.sleep(0, result=({}, [])) if offline else collect_risk_feeds(sources_cfg.get("risk_feeds") or [], client),
            asyncio.sleep(0, result=[]) if offline else discover_github_directories(
                discovery_cfg,
                client,
                known_repos={
                    "everett7623/airport-recommendations-2026",
                    "gedinked/airport-recommendation",
                    "jichangyyds-net/jichang-tuijian-shice",
                    "clashhubs/jichang-tuijian-clash",
                    "jichangx/airport-status",
                },
            ),
        )

        # Merge discovered and risk_entries cleanly with deduplication
        seen_slugs = {e["slug"] for e in catalog}
        seen_names = {re.sub(r"[\s_\-]+", "", str(e.get("name") or "").lower()) for e in catalog}
        for extra in discovered + risk_entries:
            if len(catalog) >= max_targets:
                break
            slug = make_slug(str(extra.get("name") or ""), str(extra.get("slug") or ""))
            norm_name = re.sub(r"[\s_\-]+", "", str(extra.get("name") or "").lower())
            if not slug or slug in seen_slugs or (norm_name and norm_name in seen_names):
                continue
            seen_slugs.add(slug)
            if norm_name:
                seen_names.add(norm_name)
            extra_copy = dict(extra)
            extra_copy["slug"] = slug
            catalog.append(extra_copy)

        await resolve_missing_official_urls(
            catalog,
            cache_path=data_dir / "official_cache.json",
            offline=offline,
            concurrency=6,
            ttl_days=14,
        )

        sem = asyncio.Semaphore(int(http_cfg.get("max_concurrency", 12)))

        async def _process_one(entry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
            slug = entry["slug"]
            website = str(entry.get("website") or "#").strip()
            tg_channel = str((entry.get("telegram") or {}).get("channel") or "").strip()
            sub_url = secret_subs.get(slug) or str(entry.get("public_subscription_url") or "").strip()
            skip_web = bool(entry.get("is_risk_entry")) or website == "#"

            if offline:
                web_res = WebHealthResult(url=website, ok=not skip_web, dns_ok=True, tls_ok=True, http_status=200, ttfb_ms=85.0)
                tg_res = TelegramResult(channel=tg_channel)
                sub_res = SubProbeResult()
            else:
                async with sem:
                    web_task = (
                        asyncio.sleep(0, result=WebHealthResult(url=website))
                        if skip_web
                        else probe_website(website, client)
                    )
                    tg_task = asyncio.sleep(0, result=TelegramResult())
                    sub_task = (
                        probe_subscription(
                            slug=slug,
                            sub_url=sub_url,
                            http_client=client,
                            sample_size=int(probe_cfg.get("tcp_sample_size", 16)),
                            tcp_timeout_sec=float(probe_cfg.get("tcp_timeout_sec", 4.0)),
                            enable_cli_speedtest=bool(probe_cfg.get("enable_cli_speedtest", False)),
                        )
                        if sub_url
                        else asyncio.sleep(0, result=SubProbeResult())
                    )
                    web_res, tg_res, sub_res = await asyncio.gather(web_task, tg_task, sub_task)

            norm_name = re.sub(r"[\s_\-]+", "", str(entry.get("name") or "").lower())
            risk_reason = str(entry.get("risk_reason") or risk_map.get(slug) or risk_map.get(norm_name) or "")
            prev_target_state = state["targets"].get(slug, {})
            airport_rec, next_target_state = evaluate_target(entry, web_res, tg_res, sub_res, risk_reason, prev_target_state, now)
            return airport_rec, next_target_state, tg_res.deals

        results = await asyncio.gather(*(_process_one(e) for e in catalog))

    airports: list[dict[str, Any]] = []
    deals: list[dict[str, Any]] = []
    seen_deals: set[tuple[str, str]] = set()
    for d in catalog_deals:
        key = (d["airportSlug"], d["code"])
        if key not in seen_deals:
            seen_deals.add(key)
            deals.append(d)

    for airport_rec, next_target_state, target_deals in results:
        airports.append(airport_rec)
        state["targets"][airport_rec["slug"]] = next_target_state
        for d in target_deals:
            key = (d["airportSlug"], d["code"])
            if key not in seen_deals:
                seen_deals.add(key)
                deals.append(d)

    airports.sort(key=lambda x: x["score"], reverse=True)
    monthly_report = build_monthly_report(airports, now)
    news_dicts = [n.to_dict() for n in news_list]

    snapshot = export_all(data_dir, airports, deals, news_dicts, monthly_report, state, now)
    if readme_path is not None:
        update_readme_dashboard(readme_path, airports, snapshot["stats"]["updatedAt"])
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lbird", description="LBird机场测评 自动化采集与评估 CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="执行采集、探测、评分与 JSON 导出")
    p_run.add_argument("--config-dir", type=Path, default=Path("config"))
    p_run.add_argument("--data-dir", type=Path, default=Path("data"))
    p_run.add_argument("--readme", type=Path, default=Path("README.md"))
    p_run.add_argument("--offline", action="store_true", help="离线演练模式（不发外网请求）")

    p_val = sub.add_parser("validate", help="校验导出 JSON 结构与防泄密检查")
    p_val.add_argument("--data-dir", type=Path, default=Path("data"))

    args = parser.parse_args(argv)
    if args.cmd == "run":
        snap = asyncio.run(run_pipeline(args.config_dir, args.data_dir, args.readme, offline=args.offline))
        print(json.dumps({"ok": True, "stats": snap["stats"], "news": len(snap["news"]), "deals": len(snap["deals"])}, ensure_ascii=False))
        return 0

    if args.cmd == "validate":
        errs = validate_data_dir(args.data_dir)
        if errs:
            print(json.dumps({"ok": False, "errors": errs}, ensure_ascii=False), file=sys.stderr)
            return 1
        print(json.dumps({"ok": True, "errors": []}, ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
