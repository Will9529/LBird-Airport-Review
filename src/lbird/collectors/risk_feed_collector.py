from __future__ import annotations

import json
import re
from typing import Any

from lbird.http_client import PoliteHttpClient


async def collect_risk_feeds(feeds: list[dict[str, Any]], http_client: PoliteHttpClient) -> dict[str, str]:
    """Fetch optional external risk/outage feeds and return {slug_or_domain: reason}."""
    risks: dict[str, str] = {}
    for feed in feeds or []:
        if not isinstance(feed, dict) or not feed.get("url"):
            continue
        resp = await http_client.get(str(feed["url"]), check_robots=False)
        if not resp.ok or not resp.text:
            continue
        fmt = str(feed.get("format") or "json").lower()
        try:
            if fmt == "json":
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
    return risks
