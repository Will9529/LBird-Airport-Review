from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from lbird import DISCLAIMER_SHORT, SCHEMA_VERSION
from lbird.models import ReportRecord


FORBIDDEN_SECRET_PATTERNS = [
    re.compile(r"vmess://", re.I),
    re.compile(r"vless://", re.I),
    re.compile(r"trojan://", re.I),
    re.compile(r"hysteria2://", re.I),
    re.compile(r"hy2://", re.I),
    re.compile(r"tuic://", re.I),
    re.compile(r"\bss://[A-Za-z0-9+/=_-]{8,}", re.I),
    re.compile(r"LBIRD_SUBSCRIPTIONS_JSON", re.I),
]

DASHBOARD_START = "<!-- AUTO_DASHBOARD_START -->"
DASHBOARD_END = "<!-- AUTO_DASHBOARD_END -->"


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json_or(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def export_all(
    data_dir: Path,
    airports: list[dict[str, Any]],
    deals: list[dict[str, Any]],
    news: list[dict[str, Any]],
    monthly_report: ReportRecord,
    state: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    cst = now.astimezone(timezone(timedelta(hours=8)))

    existing_reports = load_json_or(data_dir / "reports.json", [])
    if not isinstance(existing_reports, list):
        existing_reports = []
    reports_map = {r["month"]: r for r in existing_reports if isinstance(r, dict) and r.get("month")}
    reports_map[monthly_report.month] = monthly_report.to_dict()
    reports = sorted(reports_map.values(), key=lambda r: r["month"], reverse=True)

    total_probes = sum(int(v.get("total_probes") or 0) for v in state.get("targets", {}).values())
    stats = {
        "monitored": len(airports),
        "speedTests": total_probes,
        "updatedAt": cst.strftime("%Y-%m-%d %H:%M UTC+8"),
    }

    for ap in airports:
        if isinstance(ap, dict):
            ap.pop("rawSourceUrl", None)

    risk_list = [a for a in airports if a.get("status") in ("risk", "watch")]

    snapshot = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": now.isoformat(),
        "source": "Will9529/LBird-Airport-Review",
        "disclaimer": DISCLAIMER_SHORT,
        "stats": stats,
        "airports": airports,
        "deals": deals,
        "news": news,
        "reports": reports,
    }
    snapshot_v2 = {**snapshot, "schemaVersion": "2.0"}

    _write_json(data_dir / "airports.json", airports)
    _write_json(data_dir / "deals.json", deals)
    _write_json(data_dir / "news.json", news)
    _write_json(data_dir / "risk.json", risk_list)
    _write_json(data_dir / "reports.json", reports)
    _write_json(data_dir / "stats.json", stats)
    _write_json(data_dir / "snapshot.json", snapshot)
    _write_json(data_dir / "snapshot-v2.json", snapshot_v2)
    _write_json(data_dir / "state.json", state)
    return snapshot


def render_dashboard_markdown(airports: list[dict[str, Any]], updated_at: str) -> str:
    normal_cnt = sum(1 for a in airports if a.get("status") == "normal")
    watch_cnt = sum(1 for a in airports if a.get("status") == "watch")
    risk_cnt = sum(1 for a in airports if a.get("status") == "risk")

    lines = [
        f"> 最近一次自动探测时间：`{updated_at}`（共收录 `{len(airports)}` 个观测目标：🟢 正常 `{normal_cnt}` · 🟡 观察 `{watch_cnt}` · 🔴 风险 `{risk_cnt}`；纯技术学习用途，不构成任何建议）",
        "",
        "### 观测榜单节选（Top 30，完整全量见 [`data/airports.json`](./data/airports.json)）",
        "",
        "| 目标 | 状态 | 综合分 | 节点数 | 延迟 (ms) | 可用率 | 采集模式 |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    active = [a for a in airports if a.get("status") != "risk"]
    for a in sorted(active, key=lambda x: x.get("score", 0), reverse=True)[:30]:
        st = a.get("status", "normal")
        badge = "🟢 normal" if st == "normal" else "🟡 watch"
        hist = a.get("history") or {}
        lat = (hist.get("latency") or [0])[-1]
        up = (hist.get("uptime") or [0])[-1]
        mode = (a.get("probeMeta") or {}).get("mode", "web_health")
        site = a.get("website", "#")
        title_col = f"[{a['name']}]({site})" if site != "#" else a["name"]
        lines.append(
            f"| {title_col} | {badge} | **{a['score']:.2f}** | {a.get('nodes', 0)} | {lat} | {up}% | `{mode}` |"
        )

    risk_list = [a for a in airports if a.get("status") == "risk"]
    if risk_list:
        lines.extend([
            "",
            f"### 风险与跑路预警节选（共 `{len(risk_list)}` 条，完整见 [`data/risk.json`](./data/risk.json)）",
            "",
            "| 目标 | 状态 | 综合分 | 说明 |",
            "| :--- | :---: | :---: | :--- |",
        ])
        for a in risk_list[:15]:
            lines.append(f"| {a['name']} | 🔴 risk | **{a['score']:.2f}** | {a.get('summary', '')} |")
    return "\n".join(lines)


def update_readme_dashboard(readme_path: Path, airports: list[dict[str, Any]], updated_at: str) -> None:
    if not readme_path.exists():
        return
    content = readme_path.read_text(encoding="utf-8")
    if DASHBOARD_START not in content or DASHBOARD_END not in content:
        return
    table_md = render_dashboard_markdown(airports, updated_at)
    new_block = f"{DASHBOARD_START}\n{table_md}\n{DASHBOARD_END}"
    pattern = re.compile(rf"{re.escape(DASHBOARD_START)}.*?{re.escape(DASHBOARD_END)}", re.S)
    readme_path.write_text(pattern.sub(new_block, content, count=1), encoding="utf-8")


def validate_data_dir(data_dir: Path) -> list[str]:
    errors: list[str] = []
    required_files = ["airports.json", "deals.json", "news.json", "risk.json", "reports.json", "stats.json", "snapshot.json"]
    for fname in required_files:
        fpath = data_dir / fname
        if not fpath.exists():
            errors.append(f"missing_file:{fname}")
            continue
        raw = fpath.read_text(encoding="utf-8")
        for pat in FORBIDDEN_SECRET_PATTERNS:
            if pat.search(raw):
                errors.append(f"secret_leak_detected:{fname}:{pat.pattern}")
        try:
            json.loads(raw)
        except Exception as exc:
            errors.append(f"invalid_json:{fname}:{exc}")

    snap_path = data_dir / "snapshot.json"
    if snap_path.exists():
        try:
            snap = json.loads(snap_path.read_text(encoding="utf-8"))
            if snap.get("schemaVersion") != SCHEMA_VERSION:
                errors.append("bad_schema_version")
            for ap in snap.get("airports", []):
                sc = ap.get("score")
                if not isinstance(sc, (int, float)) or not (0 <= sc <= 100):
                    errors.append(f"invalid_score:{ap.get('slug')}")
                if "rawSourceUrl" in ap:
                    errors.append(f"raw_source_url_leaked:{ap.get('slug')}")
                if "未测(数据中心IP)" in (ap.get("streaming") or []):
                    errors.append(f"dirty_streaming_label:{ap.get('slug')}")
                if ap.get("dataTier") not in {"sub_probed", "web_monitored", "directory_only", "risk_listed"}:
                    errors.append(f"invalid_data_tier:{ap.get('slug')}")
                for req_k in ("slug", "name", "status", "score", "scores", "history", "plans", "routes", "regions", "clients", "streaming", "summary", "website"):
                    if req_k not in ap:
                        errors.append(f"missing_legacy_key:{ap.get('slug')}:{req_k}")
                if not isinstance(sc, (int, float)) or sc < 0 or sc > 100:
                    errors.append(f"score_out_of_range:{ap.get('slug')}")
        except Exception as exc:
            errors.append(f"snapshot_parse_error:{exc}")
    return errors
