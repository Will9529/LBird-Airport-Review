from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

from lbird.http_client import PoliteHttpClient
from lbird.models import NewsRecord


ATOM_NS = "{http://www.w3.org/2005/Atom}"
PRERELEASE_RE = re.compile(r"(?i)\b(alpha|beta|rc\d*|pre-?release|nightly|dev)\b")


def _clean_content(raw: str, url: str = "", max_len: int = 1200) -> str:
    soup = BeautifulSoup(raw or "", "html.parser")
    lines = [ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip()]
    text = "\n".join(lines)
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    if not text:
        text = "版本更新与变更日志发布。"
    if url:
        text = f"{text}\n\n官方发布页：{url}"
    return text


def _normalize_title(title: str, project_name: str) -> str:
    t = title.strip()
    if project_name and project_name.lower() not in t.lower():
        return f"{project_name} {t}"[:140]
    return t[:140]


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


def parse_feed_xml(xml_text: str, category: str, limit: int = 8, project_name: str = "") -> list[NewsRecord]:
    records: list[NewsRecord] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return records

    entries = root.findall(f"{ATOM_NS}entry")
    if entries:
        for ent in entries:
            if len(records) >= limit:
                break
            raw_title = (ent.findtext(f"{ATOM_NS}title") or "").strip()
            if not raw_title or PRERELEASE_RE.search(raw_title):
                continue
            summary = ent.findtext(f"{ATOM_NS}content") or ent.findtext(f"{ATOM_NS}summary") or ""
            updated = ent.findtext(f"{ATOM_NS}updated") or ent.findtext(f"{ATOM_NS}published") or ""
            link_el = ent.find(f"{ATOM_NS}link")
            url = link_el.attrib.get("href", "") if link_el is not None else ""
            title = _normalize_title(raw_title, project_name)
            nid = "n-" + hashlib.sha1(f"{category}:{title}".encode("utf-8")).hexdigest()[:10]
            records.append(
                NewsRecord(
                    id=nid,
                    category=category,
                    title=title,
                    summary=_clean_html(summary),
                    date=_format_date(updated),
                    url=url,
                    content=_clean_content(summary, url),
                )
            )
        return records

    for item in root.findall(".//item"):
        if len(records) >= limit:
            break
        raw_title = (item.findtext("title") or "").strip()
        if not raw_title or PRERELEASE_RE.search(raw_title):
            continue
        summary = item.findtext("description") or ""
        pub_date = item.findtext("pubDate") or ""
        url = (item.findtext("link") or "").strip()
        title = _normalize_title(raw_title, project_name)
        nid = "n-" + hashlib.sha1(f"{category}:{title}".encode("utf-8")).hexdigest()[:10]
        records.append(
            NewsRecord(
                id=nid,
                category=category,
                title=title,
                summary=_clean_html(summary),
                date=_format_date(pub_date),
                url=url,
                content=_clean_content(summary, url),
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
        proj = str(feed.get("name") or "").strip()
        resp = await http_client.get(url, check_robots=False)
        if not resp.ok or not resp.text:
            continue
        for rec in parse_feed_xml(resp.text, cat, project_name=proj):
            key = rec.title.lower()
            if key not in seen_titles:
                seen_titles.add(key)
                all_items.append(rec)
    all_items.sort(key=lambda x: x.date, reverse=True)
    return all_items[:30]
