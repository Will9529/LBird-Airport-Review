from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from lbird.collectors.catalog_collector import AFF_SHORTENERS, REVIEW_HOST_STRIP
from lbird.http_client import is_safe_public_url

BLOCKED_RESOLVED_HOSTS = (
    AFF_SHORTENERS
    | REVIEW_HOST_STRIP
    | {
        "github.com",
        "t.me",
        "telegram.me",
        "cloudflare.com",
        "jichangcnweb.com",
        "jctuijian.com",
        "duyaoss.com",
        "gate-rank.com",
        "example.com",
    }
)


def normalize_cache_key(name: str, slug: str = "") -> str:
    raw = (name or slug or "").strip().lower()
    raw = re.sub(r"[\s_\-·•・|｜/\\()（）\[\]【】]+", "", raw)
    return raw or slug.strip().lower()


def is_valid_resolved_origin(url_str: str) -> bool:
    if not url_str or not is_safe_public_url(url_str):
        return False
    try:
        host = (urlparse(url_str).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    for blocked in BLOCKED_RESOLVED_HOSTS:
        if host == blocked or host.endswith("." + blocked):
            return False
    return True


async def resolve_final_origin(raw_url: str, timeout_sec: float = 8.0) -> str:
    current = (raw_url or "").strip()
    if not current.startswith(("http://", "https://")):
        return ""
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_sec),
            follow_redirects=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LBrid-Resolver/2.0",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        ) as client:
            for _ in range(4):
                if not is_safe_public_url(current):
                    return ""
                resp = await client.get(current)
                if 300 <= resp.status_code < 400:
                    loc = resp.headers.get("location")
                    if not loc:
                        break
                    current = urljoin(current, loc)
                    continue
                break
        if not is_safe_public_url(current):
            return ""
        parsed = urlparse(current)
        origin = f"{parsed.scheme}://{parsed.netloc}/"
        return origin if is_valid_resolved_origin(origin) else ""
    except Exception:
        return ""


def _load_cache(cache_path: Path) -> dict[str, dict[str, Any]]:
    if not cache_path.exists():
        return {}
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_cache(cache_path: Path, cache: dict[str, dict[str, Any]]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _is_fresh(entry: dict[str, Any], ttl_days: int, now: datetime) -> bool:
    url = str(entry.get("officialUrl") or "").strip()
    if not is_valid_resolved_origin(url):
        return False
    ts = str(entry.get("resolvedAt") or "").strip()
    if not ts:
        return False
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (now - dt) < timedelta(days=ttl_days)
    except Exception:
        return False


async def resolve_missing_official_urls(
    catalog: list[dict[str, Any]],
    cache_path: Path,
    offline: bool = False,
    concurrency: int = 6,
    ttl_days: int = 14,
) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    cache = _load_cache(cache_path)
    cache_hits = 0
    resolved_live = 0

    to_resolve: list[tuple[dict[str, Any], str, str]] = []
    for entry in catalog:
        if entry.get("is_risk_entry"):
            continue
        website = str(entry.get("website") or "#").strip()
        if website and website != "#" and is_valid_resolved_origin(website):
            entry["officialUrl"] = website
            continue

        key = normalize_cache_key(str(entry.get("name") or ""), str(entry.get("slug") or ""))
        cached = cache.get(key) or cache.get(str(entry.get("slug") or ""))
        if isinstance(cached, dict) and _is_fresh(cached, ttl_days, now):
            official = str(cached["officialUrl"])
            entry["website"] = official
            entry["officialUrl"] = official
            cache_hits += 1
            continue

        raw_src = str(entry.get("rawSourceUrl") or "").strip()
        if not offline and raw_src.startswith(("http://", "https://")):
            to_resolve.append((entry, key, raw_src))

    if to_resolve:
        sem = asyncio.Semaphore(max(1, min(8, concurrency)))

        async def _worker(item: tuple[dict[str, Any], str, str]) -> None:
            nonlocal resolved_live
            entry, key, raw_src = item
            async with sem:
                origin = await resolve_final_origin(raw_src)
            if origin:
                entry["website"] = origin
                entry["officialUrl"] = origin
                cache[key] = {
                    "officialUrl": origin,
                    "resolvedAt": now.isoformat(),
                    "sourceHost": (urlparse(raw_src).hostname or "").lower(),
                }
                resolved_live += 1

        await asyncio.gather(*(_worker(it) for it in to_resolve))
        _save_cache(cache_path, cache)

    for entry in catalog:
        entry.pop("rawSourceUrl", None)

    return {"cacheHits": cache_hits, "resolvedLive": resolved_live, "attempted": len(to_resolve)}
