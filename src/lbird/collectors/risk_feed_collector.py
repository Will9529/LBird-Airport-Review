from __future__ import annotations

import json
import re
from typing import Any

from lbird.collectors.catalog_collector import make_slug
from lbird.http_client import PoliteHttpClient


def parse_jichangx_markdown(raw_text: str) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Parse jichangx/airport-status README table into (risk_map, risk_entries)."""
    risk_map: dict[str, str] = {}
    risk_entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    for line in raw_text.splitlines():
        s = line.strip()
        if not s.startswith("|") or s.startswith("| 名字") or re.match(r"^\|[\s:|\-]+\|$", s):
            continue
        cols = [c.strip() for c in s.strip("|").split("|")]
        if len(cols) < 4:
            continue
        raw_name = re.sub(r"[~*`]", "", cols[0]).strip()
        if not raw_name or raw_name == "名字":
            continue
        # Strip parenthetical notes for key normalization while keeping display name
        primary_name = raw_name.split("（")[0].split("(")[0].strip() or raw_name
        level = re.sub(r"[~*`]", "", cols[2]).strip() or "跑路预警"
        year = re.sub(r"[^0-9]", "", cols[3])[:4] or "2025"

        slug = make_slug(primary_name)
        if not slug or slug in seen:
            continue
        seen.add(slug)

        reason = f"社区公开风险清单记录：{level}（{year}）。"
        norm_key = re.sub(r"[\s_\-]+", "", primary_name.lower())
        risk_map[slug] = reason
        if norm_key:
            risk_map[norm_key] = reason

        risk_entries.append(
            {
                "slug": slug,
                "name": primary_name[:80],
                "website": "#",
                "priceMonthly": 10.0,
                "founded": f"{year}-01",
                "tags": ["跑路预警", "社区反馈"],
                "routes": ["中转"],
                "is_risk_entry": True,
                "risk_reason": reason,
                "summary": reason,
            }
        )
    return risk_map, risk_entries


async def collect_risk_feeds(
    feeds: list[dict[str, Any]],
    http_client: PoliteHttpClient,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Fetch external risk/outage feeds and return (risk_map, risk_entries)."""
    risks: dict[str, str] = {}
    entries: list[dict[str, Any]] = []

    for feed in feeds or []:
        if not isinstance(feed, dict) or not feed.get("url"):
            continue
        resp = await http_client.get(str(feed["url"]), check_robots=False)
        if not resp.ok or not resp.text:
            continue
        fmt = str(feed.get("format") or "json").lower()
        try:
            if fmt == "jichangx_markdown":
                r_map, r_entries = parse_jichangx_markdown(resp.text)
                risks.update(r_map)
                entries.extend(r_entries)
            elif fmt == "json":
                data = json.loads(resp.text)
                items = data if isinstance(data, list) else data.get("items", [])
                for it in items:
                    if isinstance(it, dict):
                        key = str(it.get("slug") or it.get("domain") or "").strip().lower()
                        reason = str(it.get("reason") or "外部风险源预警").strip()
                        if key:
                            risks[key] = reason
            elif fmt == "markdown":
                for line in resp.text.splitlines():
                    m = re.match(r"^[-*]\s+`?([a-z0-9.-]+)`?\s*[:：-]?\s*(.*)$", line.strip(), re.I)
                    if m:
                        risks[m.group(1).lower()] = m.group(2).strip() or "外部风险源预警"
        except Exception:
            continue
    return risks, entries
