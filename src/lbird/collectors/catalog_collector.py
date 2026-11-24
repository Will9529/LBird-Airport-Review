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
REVIEW_HOST_STRIP = {"jichangyyds.com", "www.jichangyyds.com", "vpsknow.com", "www.vpsknow.com"}
AFF_QUERY_KEYS = {"aff", "code", "ref", "invite", "invite_code", "from", "utm_source", "utm_medium", "utm_campaign"}
ROUTE_KEYWORDS = ("IEPL", "IPLC", "CN2", "BGP", "中转")
STREAMING_KEYWORDS = ("Netflix", "ChatGPT", "Disney+", "YouTube", "TikTok")
PRICE_MONTHLY_RE = re.compile(r"[¥￥]\s*(\d+(?:\.\d+)?)\s*(?:/\s*(月|年)|起)?", re.I)
EXPLICIT_MONTHLY_RE = re.compile(r"[¥￥]\s*(\d+(?:\.\d+)?)\s*/\s*月", re.I)
NODES_TEXT_RE = re.compile(r"(\d{1,4})\s*[+＋]?\s*(?:个|条)?\s*节点")
AVAIL_TOTAL_RE = re.compile(r"(\d{1,4})\s*/\s*(\d{1,4})")
SPEED_MBS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*MB/s", re.I)
LATENCY_MS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*ms", re.I)
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
    blocked_hosts = AFF_SHORTENERS | REVIEW_HOST_STRIP
    if not host or host in blocked_hosts or any(host.endswith("." + d) for d in blocked_hosts):
        return "#"
    clean_qs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False) if k.lower() not in AFF_QUERY_KEYS]
    frag = "" if parsed.fragment.startswith("/register") else parsed.fragment
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(clean_qs), frag))


def parse_monthly_price(pricing_text: str, default: float = 15.0) -> float:
    text = (pricing_text or "").strip()
    if not text:
        return default
    explicit_m = EXPLICIT_MONTHLY_RE.search(text)
    if explicit_m:
        return max(0.0, min(999.0, float(explicit_m.group(1))))
    m = PRICE_MONTHLY_RE.search(text)
    if not m:
        return default
    val = float(m.group(1))
    unit = (m.group(2) or "").strip()
    has_annual_hint = unit == "年" or (("/年" in text or "年付" in text) and "月付" not in text and "/月" not in text)
    if unit == "年" or (has_annual_hint and val >= 40.0):
        val = round(val / 12.0, 2)
    return max(0.0, min(999.0, val))


def parse_routes_from_text(text: str) -> list[str]:
    upper = (text or "").upper()
    routes = [r for r in ROUTE_KEYWORDS if r.upper() in upper]
    return routes or ["BGP"]


def parse_nodes_from_text(text: str) -> int:
    m = NODES_TEXT_RE.search(text or "")
    if m:
        return int(m.group(1))
    return 0


def parse_streaming_from_text(text: str) -> list[str]:
    lower = (text or "").lower()
    found = [s for s in STREAMING_KEYWORDS if s.lower() in lower]
    return found


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _strip_jsonc(raw_text: str) -> Any:
    cleaned = [ln for ln in raw_text.splitlines() if not ln.lstrip().startswith("//")]
    return json.loads("\n".join(cleaned))


def parse_markdown_table(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    lines = [ln.strip() for ln in text.splitlines()]
    if len(lines) < 3:
        return rows

    i = 0
    while i < len(lines) - 2:
        if not lines[i].startswith("|") or not lines[i + 1].startswith("|"):
            i += 1
            continue
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

        name_idx = _find_col("机场", "名称", "名字", "name", "provider", "服务")
        url_idx = _find_col("官网", "链接", "url", "website", "直达", "地址")
        price_idx = _find_col("价格", "月付", "套餐", "起价", "price", "起步")
        route_idx = _find_col("线路", "类型", "route", "line", "选择重点")
        nodes_idx = _find_col("节点数", "nodes")

        if name_idx == -1:
            i += 2
            continue

        j = i + 2
        while j < len(lines) and lines[j].startswith("|") and not re.match(r"^\|[\s:|\-]+\|$", lines[j]):
            cols = [c.strip() for c in lines[j].strip("|").split("|")]
            if len(cols) == len(header_cols):
                raw_name_cell = cols[name_idx]
                link_in_name = MD_LINK_RE.search(raw_name_cell)
                clean_name = re.sub(r"[*`~⚠️]", "", link_in_name.group(1) if link_in_name else raw_name_cell).strip()
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
                    nodes_val = 0
                    if nodes_idx != -1 and cols[nodes_idx].isdigit():
                        nodes_val = int(cols[nodes_idx])
                    elif price_idx != -1:
                        nodes_val = parse_nodes_from_text(cols[price_idx] + " " + route_str)
                    rows.append(
                        {
                            "slug": make_slug(clean_name),
                            "name": clean_name[:80],
                            "website": sanitize_website_url(raw_url),
                            "priceMonthly": price_val,
                            "nodes": nodes_val,
                            "routes": parse_routes_from_text(route_str),
                            "tags": ["目录收录", "公开索引"],
                            "summary": f"来自公开开源目录索引（参考线路：{'/'.join(parse_routes_from_text(route_str))}）。",
                        }
                    )
            j += 1
        i = j
    return rows


def parse_jichangyyds_markdown(raw_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse all tables in jichangyyds-net/jichang-tuijian-shice README and merge by brand."""
    by_name: dict[str, dict[str, Any]] = {}
    deals: list[dict[str, Any]] = []
    lines = [ln.strip() for ln in raw_text.splitlines()]

    def _ensure_brand(cell: str) -> tuple[str, dict[str, Any]] | tuple[None, None]:
        m = MD_LINK_RE.search(cell)
        name = re.sub(r"[*`~⚠️]", "", m.group(1) if m else cell).strip()
        if not name or name in ("机场品牌", "品牌"):
            return None, None
        norm = re.sub(r"[\s_\-]+", "", name.lower())
        if norm not in by_name:
            by_name[norm] = {
                "slug": make_slug(name),
                "name": name[:80],
                "website": "#",
                "priceMonthly": 15.0,
                "nodes": 0,
                "routes": ["BGP"],
                "tags": ["目录收录", "公开索引"],
                "plans": [],
                "importMethods": [],
            }
        return norm, by_name[norm]

    i = 0
    while i < len(lines) - 2:
        if not lines[i].startswith("|") or not lines[i + 1].startswith("|"):
            i += 1
            continue
        headers = [re.sub(r"[*`_]", "", c).strip() for c in lines[i].strip("|").split("|")]
        if not re.match(r"^\|[\s:|\-]+\|$", lines[i + 1]):
            i += 1
            continue

        j = i + 2
        while j < len(lines) and lines[j].startswith("|") and not re.match(r"^\|[\s:|\-]+\|$", lines[j]):
            cols = [c.strip() for c in lines[j].strip("|").split("|")]
            if len(cols) != len(headers):
                j += 1
                continue
            row = dict(zip(headers, cols))

            if "机场品牌" in row:
                norm, entry = _ensure_brand(row["机场品牌"])
                if entry:
                    if "最低月付" in row:
                        entry["priceMonthly"] = parse_monthly_price(row["最低月付"], entry["priceMonthly"])
                    if "编辑评分" in row:
                        m_rat = re.search(r"(\d+(?:\.\d+)?)", row["编辑评分"])
                        if m_rat:
                            entry["externalRating"] = float(m_rat.group(1))
                    if "节点数" in row:
                        m_nd = re.search(r"(\d+)", row["节点数"])
                        if m_nd:
                            entry["nodes"] = max(entry["nodes"], int(m_nd.group(1)))
                    if "优惠码" in row:
                        code = row["优惠码"].strip("` ").strip()
                        if code and code not in ("—", "-", "无") and 3 <= len(code) <= 24:
                            deals.append(
                                {
                                    "airportSlug": entry["slug"],
                                    "code": code,
                                    "discount": f"券后参考 {row.get('券后', '见官网')}" if row.get("券后") not in (None, "—", "-") else "目录收录优惠码",
                                    "plans": "月付套餐",
                                    "dateRange": "以官网为准",
                                    "stackable": False,
                                    "refundable": False,
                                    "active": True,
                                }
                            )
                    if "可用/总节点" in row:
                        m_at = AVAIL_TOTAL_RE.search(row["可用/总节点"])
                        if m_at:
                            avail, total = int(m_at.group(1)), int(m_at.group(2))
                            entry["nodes"] = max(entry["nodes"], total)
                            if total > 0:
                                entry["benchUptime"] = round((avail / total) * 100.0, 2)
                    if "香港中位速度" in row:
                        m_sp = SPEED_MBS_RE.search(row["香港中位速度"])
                        if m_sp:
                            entry["benchSpeedMbps"] = round(float(m_sp.group(1)) * 8.0, 1)
                    if "香港中位延迟" in row:
                        m_lat = LATENCY_MS_RE.search(row["香港中位延迟"])
                        if m_lat:
                            entry["benchLatencyMs"] = float(m_lat.group(1))
                    if "套餐" in row and "流量" in row and "价格" in row:
                        if len(entry["plans"]) < 3:
                            entry["plans"].append(
                                {
                                    "name": row["套餐"][:30],
                                    "traffic": row["流量"][:24],
                                    "price": parse_monthly_price(row["价格"], entry["priceMonthly"]),
                                    "cycle": "月付",
                                    "devices": "详见官网",
                                }
                            )
                    if "订阅方式" in row:
                        sub_txt = row["订阅方式"]
                        if "订阅链接" in sub_txt and "暂不" not in sub_txt:
                            entry["importMethods"] = ["一键订阅", "Clash 托管"]
                        elif "客户端" in sub_txt:
                            entry["importMethods"] = ["官方客户端"]
            j += 1
        i = j

    for entry in by_name.values():
        parts = [f"参考月付 ¥{entry['priceMonthly']:.1f}"]
        if entry["nodes"] > 0:
            parts.append(f"节点 {entry['nodes']} 个")
        if "benchSpeedMbps" in entry:
            parts.append(f"实测速率 {entry['benchSpeedMbps']} Mbps")
        if "benchLatencyMs" in entry:
            parts.append(f"延迟 {entry['benchLatencyMs']:.0f} ms")
        if "externalRating" in entry:
            parts.append(f"公开参考评分 {entry['externalRating']}/5")
        entry["summary"] = "公开目录与实测数据汇总：" + "，".join(parts) + "。"

    return list(by_name.values()), deals


def parse_everett_jsonc(
    raw_text: str,
    ratings_text: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    doc = _strip_jsonc(raw_text)
    if not isinstance(doc, dict):
        return [], []

    ratings_map: dict[str, dict[str, Any]] = {}
    if ratings_text.strip():
        try:
            r_doc = _strip_jsonc(ratings_text)
            if isinstance(r_doc, dict) and isinstance(r_doc.get("airports"), dict):
                ratings_map = r_doc["airports"]
        except Exception:
            pass

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
        desc = str(item.get("description") or "")
        feats = [str(f) for f in (item.get("features") or [])]
        blob = " ".join([line_type, desc] + feats)

        tags = [str(t).strip() for t in (item.get("tags") or []) if str(t).strip()][:5]
        if "目录收录" not in tags:
            tags.append("目录收录")
        routes = parse_routes_from_text(blob)
        price = parse_monthly_price(pricing)
        nodes = parse_nodes_from_text(blob)
        streaming = parse_streaming_from_text(blob)
        trial = any("试用" in str(x) for x in (tags + feats))

        r_info = ratings_map.get(name) or {}
        stars = r_info.get("stars") if isinstance(r_info.get("stars"), (int, float)) else None

        rec: dict[str, Any] = {
            "slug": slug,
            "name": name,
            "website": sanitize_website_url(str(item.get("url") or "")),
            "priceMonthly": price,
            "nodes": nodes,
            "trial": trial,
            "routes": routes,
            "tags": tags,
            "summary": f"公开目录收录条目（参考月付 ¥{price:.1f}，线路 {'/'.join(routes)}）。",
        }
        if streaming:
            rec["streaming"] = streaming
        if stars is not None:
            rec["externalRating"] = float(stars)
        entries.append(rec)

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


def _merge_entry(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    """Merge richer metadata from secondary directory sources into existing entry."""
    if incoming.get("nodes", 0) > target.get("nodes", 0):
        target["nodes"] = incoming["nodes"]
    for key in ("benchSpeedMbps", "benchLatencyMs", "benchUptime", "externalRating"):
        if key not in target and key in incoming:
            target[key] = incoming[key]
    if not target.get("plans") and incoming.get("plans"):
        target["plans"] = incoming["plans"]
    if not target.get("streaming") and incoming.get("streaming"):
        target["streaming"] = incoming["streaming"]
    if not target.get("importMethods") and incoming.get("importMethods"):
        target["importMethods"] = incoming["importMethods"]
    if target.get("routes") == ["BGP"] and incoming.get("routes"):
        target["routes"] = incoming["routes"]
    if "实测" in str(incoming.get("summary", "")) and "实测" not in str(target.get("summary", "")):
        target["summary"] = incoming["summary"]


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
    by_slug: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}

    def _add_or_merge(raw: dict[str, Any]) -> None:
        if not isinstance(raw, dict):
            return
        name = str(raw.get("name") or "").strip()
        slug = make_slug(name, str(raw.get("slug") or ""))
        norm_name = re.sub(r"[\s_\-]+", "", name.lower())
        if not slug or slug in deny_slugs:
            return
        website = str(raw.get("website") or "#").strip()
        host = (urlparse(website).hostname or "").lower()
        if host and any(host == d or host.endswith("." + d) for d in deny_domains):
            return

        existing = by_slug.get(slug) or (by_name.get(norm_name) if norm_name else None)
        if existing is not None:
            _merge_entry(existing, raw)
            return

        item = dict(raw)
        item["slug"] = slug
        by_slug[slug] = item
        if norm_name:
            by_name[norm_name] = item
        entries.append(item)

    for raw in airports_doc.get("airports") or []:
        _add_or_merge(raw)

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
                    ratings_txt = ""
                    if feed.get("ratings_url"):
                        r_resp = await http_client.get(str(feed["ratings_url"]), check_robots=False)
                        if r_resp.ok and r_resp.text:
                            ratings_txt = r_resp.text
                    items, feed_deals = parse_everett_jsonc(resp.text, ratings_txt)
                    for it in items:
                        _add_or_merge(it)
                    extracted_deals.extend(feed_deals)
                elif fmt == "jichangyyds_markdown":
                    items, feed_deals = parse_jichangyyds_markdown(resp.text)
                    for it in items:
                        _add_or_merge(it)
                    extracted_deals.extend(feed_deals)
                elif fmt == "json":
                    parsed = json.loads(resp.text)
                    items = parsed if isinstance(parsed, list) else parsed.get("airports", [])
                    for it in items:
                        _add_or_merge(it)
                elif fmt == "yaml":
                    parsed = yaml.safe_load(resp.text)
                    items = parsed if isinstance(parsed, list) else (parsed or {}).get("airports", [])
                    for it in items:
                        _add_or_merge(it)
                elif fmt == "markdown":
                    for it in parse_markdown_table(resp.text):
                        _add_or_merge(it)
            except Exception:
                continue

    return entries, extracted_deals
