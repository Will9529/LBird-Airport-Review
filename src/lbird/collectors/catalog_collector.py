from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from lbird.http_client import PoliteHttpClient


def normalize_slug(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9-_]", "-", raw.strip().lower())
    return slug.strip("-")


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _parse_markdown_table(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 3:
        return rows
    headers = [c.strip().lower() for c in lines[0].strip("|").split("|")]
    for ln in lines[2:]:
        cols = [c.strip() for c in ln.strip("|").split("|")]
        if len(cols) != len(headers):
            continue
        item = dict(zip(headers, cols))
        name = item.get("name") or item.get("名称") or ""
        website = item.get("website") or item.get("url") or item.get("官网") or ""
        if name and website.startswith(("http://", "https://")):
            slug = normalize_slug(item.get("slug") or name)
            if slug:
                rows.append({"slug": slug, "name": name, "website": website})
    return rows


async def load_catalog(
    config_dir: Path,
    sources_cfg: dict[str, Any],
    http_client: PoliteHttpClient | None = None,
) -> list[dict[str, Any]]:
    airports_doc = load_yaml_file(config_dir / "airports.yaml")
    deny_doc = load_yaml_file(config_dir / "denylist.yaml")

    deny_slugs = {normalize_slug(str(s)) for s in (deny_doc.get("slugs") or []) if s}
    deny_domains = {str(d).strip().lower() for d in (deny_doc.get("domains") or []) if d}

    entries: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()

    def _add_entry(raw: dict[str, Any]) -> None:
        if not isinstance(raw, dict):
            return
        slug = normalize_slug(str(raw.get("slug") or raw.get("name") or ""))
        if not slug or slug in deny_slugs or slug in seen_slugs:
            return
        website = str(raw.get("website") or "").strip()
        host = (urlparse(website).hostname or "").lower()
        if host and any(host == d or host.endswith("." + d) for d in deny_domains):
            return
        seen_slugs.add(slug)
        item = dict(raw)
        item["slug"] = slug
        entries.append(item)

    for raw in airports_doc.get("airports") or []:
        _add_entry(raw)

    if http_client is not None:
        for feed in sources_cfg.get("directory_feeds") or []:
            if not isinstance(feed, dict) or not feed.get("url"):
                continue
            resp = await http_client.get(str(feed["url"]), check_robots=False)
            if not resp.ok or not resp.text:
                continue
            fmt = str(feed.get("format") or "json").lower()
            try:
                if fmt == "json":
                    parsed = json.loads(resp.text)
                    items = parsed if isinstance(parsed, list) else parsed.get("airports", [])
                    for it in items:
                        _add_entry(it)
                elif fmt == "yaml":
                    parsed = yaml.safe_load(resp.text)
                    items = parsed if isinstance(parsed, list) else (parsed or {}).get("airports", [])
                    for it in items:
                        _add_entry(it)
                elif fmt == "markdown":
                    for it in _parse_markdown_table(resp.text):
                        _add_entry(it)
            except Exception:
                continue

    return entries
