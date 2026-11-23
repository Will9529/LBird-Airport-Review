from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import yaml

from lbird.http_client import PoliteHttpClient


AFF_SHORTENERS = {"go.uukk.de", "bit.ly", "tinyurl.com", "t.cn", "is.gd", "dwz.cn"}
AFF_QUERY_KEYS = {"aff", "code", "ref", "invite", "invite_code", "from", "utm_source", "utm_medium", "utm_campaign"}
ROUTE_KEYWORDS = ("IEPL", "IPLC", "CN2", "BGP", "中转")
PRICE_MONTHLY_RE = re.compile(r"[¥￥]\s*(\d+(?:\.\d+)?)\s*(?:/\s*(月|年)|起)?", re.I)
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def make_slug(raw_name: str, raw_slug: str = "") -> str:
    candidate = (raw_slug or raw_name or "").strip().lower()
    ascii_slug = re.sub(r"[^a-z0-9-_]", "-", candidate)
    ascii_slug = re.sub(r"-{2,}", "-", ascii_slug).strip("-")
    if len(ascii_slug) >= 2 and re.search(r"[a-z0-9]", ascii_slug):
        return ascii_slug[:48]
    clean_name = re.sub(r"\s+", "", (raw_name or raw_slug or "").strip().lower())
    if not clean_name:
        return ""
    digest = hashlib.sha1(clean_name.encode("utf-8")).hexdigest()[:8]
    return f"ap-{digest}"


def normalize_slug(raw: str) -> str:
    return make_slug(raw, raw)


def sanitize_website_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw.startswith(("http://", "https://")):
        return "#"
    try:
        parsed = urlparse(raw)
    except Exception:
        return "#"
    host = (parsed.hostname or "").lower()
    if not host or host in AFF_SHORTENERS or any(host.endswith("." + d) for d in AFF_SHORTENERS):
        return "#"
    clean_qs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False) if k.lower() not in AFF_QUERY_KEYS]
    frag = "" if parsed.fragment.startswith("/register") else parsed.fragment
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(clean_qs), frag))


def parse_monthly_price(pricing_text: str, default: float = 15.0) -> float:
    text = (pricing_text or "").strip()
    if not text:
        return default
    m = PRICE_MONTHLY_RE.search(text)
    if not m:
        return default
    val = float(m.group(1))
    unit = (m.group(2) or "").strip()
    if unit == "年" or "/年" in text or "年付" in text:
        val = round(val / 12.0, 2)
    return max(0.0, min(999.0, val))


def parse_routes_from_text(text: str) -> list[str]:
    upper = (text or "").upper()
    routes = [r for r in ROUTE_KEYWORDS if r.upper() in upper]
    return routes or ["BGP"]


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def parse_markdown_table(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 3:
        return rows

    i = 0
    while i < len(lines) - 2:
        header_cols = [re.sub(r"[*`_]", "", c).strip().lower() for c in lines[i].strip("|").split("|")]
        sep_line = lines[i + 1]
        if not re.match(r"^\|[\s:|\-]+\|$", sep_line):
            i += 1
            continue

        def _find_col(*keys: str) -> int:
            for idx, h in enumerate(header_cols):
                if any(k in h for k in keys):
                    return idx
            return -1

        name_idx = _find_col("机场", "名称", "名字", "name", "provider")
        url_idx = _find_col("官网", "链接", "url", "website", "直达", "地址")
        price_idx = _find_col("价格", "月付", "套餐", "price", "起步")
        route_idx = _find_col("线路", "类型", "route", "line")

        if name_idx == -1:
            i += 2
            continue

        j = i + 2
        while j < len(lines) and not re.match(r"^\|[\s:|\-]+\|$", lines[j]):
            cols = [c.strip() for c in lines[j].strip("|").split("|")]
            if len(cols) == len(header_cols):
                raw_name_cell = cols[name_idx]
                link_in_name = MD_LINK_RE.search(raw_name_cell)
                clean_name = re.sub(r"[*`~]", "", link_in_name.group(1) if link_in_name else raw_name_cell).strip()
                raw_url = link_in_name.group(2) if link_in_name else ""
                if url_idx != -1:
                    link_in_url = MD_LINK_RE.search(cols[url_idx])
                    if link_in_url:
                        raw_url = link_in_url.group(2)
                    elif cols[url_idx].startswith(("http://", "https://")):
                        raw_url = cols[url_idx]

                if clean_name and not clean_name.startswith("---"):
                    price_val = parse_monthly_price(cols[price_idx]) if price_idx != -1 else 15.0
                    route_str = cols[route_idx] if route_idx != -1 else ""
                    rows.append(
                        {
                            "slug": make_slug(clean_name),
                            "name": clean_name[:80],
                            "website": sanitize_website_url(raw_url),
                            "priceMonthly": price_val,
                            "routes": parse_routes_from_text(route_str),
                            "tags": ["目录收录", "公开索引"],
                            "summary": f"来自公开开源目录索引（参考线路：{'/'.join(parse_routes_from_text(route_str))}）。",
                        }
                    )
            j += 1
        i = j
    return rows


def parse_everett_jsonc(raw_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cleaned_lines = [ln for ln in raw_text.splitlines() if not ln.lstrip().startswith("//")]
    doc = json.loads("\n".join(cleaned_lines))
    if not isinstance(doc, dict):
        return [], []

    entries: list[dict[str, Any]] = []
    deals: list[dict[str, Any]] = []

    def _convert_active(item: dict[str, Any]) -> None:
        if not isinstance(item, dict):
            return
        name = str(item.get("name") or "").strip()
        if not name:
            return
        slug = make_slug(name)
        pricing = str(item.get("pricing") or "")
        line_type = str(item.get("lineType") or "")
        tags = [str(t).strip() for t in (item.get("tags") or []) if str(t).strip()][:5]
        if "目录收录" not in tags:
            tags.append("目录收录")
        routes = parse_routes_from_text(line_type + " " + " ".join(item.get("features") or []))
        price = parse_monthly_price(pricing)
        trial = any("试用" in str(x) for x in (tags + (item.get("features") or [])))
        entries.append(
            {
                "slug": slug,
                "name": name,
                "website": sanitize_website_url(str(item.get("url") or "")),
                "priceMonthly": price,
                "trial": trial,
                "routes": routes,
                "tags": tags,
                "summary": f"公开目录收录条目（参考月付 ¥{price:.1f}，线路 {'/'.join(routes)}）。",
            }
        )
        coupon = str(item.get("coupon") or "").strip()
        if coupon and 3 <= len(coupon) <= 24:
            deals.append(
                {
                    "airportSlug": slug,
                    "code": coupon,
                    "discount": "目录收录优惠码",
                    "plans": pricing or "详见官网",
                    "dateRange": "长期/以官网为准",
                    "stackable": False,
                    "refundable": False,
                    "active": True,
                }
            )

    cats = doc.get("categories")
    if isinstance(cats, dict):
        for lst in cats.values():
            if isinstance(lst, list):
                for it in lst:
                    _convert_active(it)

    for key in ("no_aff", "directory_only"):
        lst = doc.get(key)
        if isinstance(lst, list):
            for it in lst:
                _convert_active(it)

    defunct = doc.get("defunct")
    if isinstance(defunct, list):
        for it in defunct:
            if not isinstance(it, dict):
                continue
            name = str(it.get("name") or "").strip()
            if not name:
                continue
            slug = make_slug(name)
            d_date = str(it.get("defunctDate") or "").strip()
            entries.append(
                {
                    "slug": slug,
                    "name": name,
                    "website": "#",
                    "priceMonthly": parse_monthly_price(str(it.get("pricingWas") or ""), 10.0),
                    "founded": d_date[:7] if len(d_date) >= 7 else "2024-01",
                    "routes": parse_routes_from_text(str(it.get("lineType") or "")),
                    "tags": ["风险观察", "目录预警"],
                    "is_risk_entry": True,
                    "risk_reason": f"公开目录记录已下架/停止收录（{d_date or '历史'}）。",
                    "summary": f"公开目录记录已下架/停止收录（{d_date or '历史'}），仅供参考避坑。",
                }
            )

    return entries, deals


async def load_catalog(
    config_dir: Path,
    sources_cfg: dict[str, Any],
    http_client: PoliteHttpClient | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    airports_doc = load_yaml_file(config_dir / "airports.yaml")
    deny_doc = load_yaml_file(config_dir / "denylist.yaml")

    deny_slugs = {make_slug(str(s), str(s)) for s in (deny_doc.get("slugs") or []) if s}
    deny_domains = {str(d).strip().lower() for d in (deny_doc.get("domains") or []) if d}

    entries: list[dict[str, Any]] = []
    extracted_deals: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    seen_names: set[str] = set()

    def _add_entry(raw: dict[str, Any]) -> None:
        if not isinstance(raw, dict):
            return
        name = str(raw.get("name") or "").strip()
        slug = make_slug(name, str(raw.get("slug") or ""))
        norm_name = re.sub(r"[\s_\-]+", "", name.lower())
        if not slug or slug in deny_slugs or slug in seen_slugs or (norm_name and norm_name in seen_names):
            return
        website = str(raw.get("website") or "#").strip()
        host = (urlparse(website).hostname or "").lower()
        if host and any(host == d or host.endswith("." + d) for d in deny_domains):
            return
        seen_slugs.add(slug)
        if norm_name:
            seen_names.add(norm_name)
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
                if fmt == "everett_jsonc":
                    items, feed_deals = parse_everett_jsonc(resp.text)
                    for it in items:
                        _add_entry(it)
                    extracted_deals.extend(feed_deals)
                elif fmt == "json":
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
                    for it in parse_markdown_table(resp.text):
                        _add_entry(it)
            except Exception:
                continue

    return entries, extracted_deals
