from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

from lbird.http_client import PoliteHttpClient
from lbird.models import NewsRecord


ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _clean_html(raw: str, max_len: int = 140) -> str:
    text = BeautifulSoup(raw or "", "html.parser").get_text(" ", strip=True)
    text = " ".join(text.split())
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "…"
    return text or "版本更新与变更日志发布。"


def _format_date(raw_date: str) -> str:
    s = (raw_date or "").strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10].replace("-", "/")
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(s)
        return dt.strftime("%Y/%m/%d")
    except Exception:
        return datetime.utcnow().strftime("%Y/%m/%d")


def parse_feed_xml(xml_text: str, category: str, limit: int = 8) -> list[NewsRecord]:
    records: list[NewsRecord] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return records

    entries = root.findall(f"{ATOM_NS}entry")
    if entries:
        for ent in entries[:limit]:
            title = (ent.findtext(f"{ATOM_NS}title") or "").strip()
            summary = ent.findtext(f"{ATOM_NS}content") or ent.findtext(f"{ATOM_NS}summary") or ""
            updated = ent.findtext(f"{ATOM_NS}updated") or ent.findtext(f"{ATOM_NS}published") or ""
            link_el = ent.find(f"{ATOM_NS}link")
            url = link_el.attrib.get("href", "") if link_el is not None else ""
            if not title:
                continue
            nid = "n-" + hashlib.sha1(f"{category}:{title}".encode("utf-8")).hexdigest()[:10]
            records.append(
                NewsRecord(
                    id=nid,
                    category=category,
                    title=title[:140],
                    summary=_clean_html(summary),
                    date=_format_date(updated),
                    url=url,
                )
            )
        return records

    for item in root.findall(".//item")[:limit]:
        title = (item.findtext("title") or "").strip()
        summary = item.findtext("description") or ""
        pub_date = item.findtext("pubDate") or ""
        url = (item.findtext("link") or "").strip()
        if not title:
            continue
        nid = "n-" + hashlib.sha1(f"{category}:{title}".encode("utf-8")).hexdigest()[:10]
        records.append(
            NewsRecord(
                id=nid,
                category=category,
                title=title[:140],
                summary=_clean_html(summary),
                date=_format_date(pub_date),
                url=url,
            )
        )
    return records


async def collect_news(feeds: list[dict[str, Any]], http_client: PoliteHttpClient) -> list[NewsRecord]:
    all_items: list[NewsRecord] = []
    seen_titles: set[str] = set()
    for feed in feeds or []:
        if not isinstance(feed, dict) or not feed.get("url"):
            continue
        url = str(feed["url"])
        cat = str(feed.get("category") or "行业动态")
        resp = await http_client.get(url, check_robots=False)
        if not resp.ok or not resp.text:
            continue
        for rec in parse_feed_xml(resp.text, cat):
            key = rec.title.lower()
            if key not in seen_titles:
                seen_titles.add(key)
                all_items.append(rec)
    all_items.sort(key=lambda x: x.date, reverse=True)
    return all_items[:30]
