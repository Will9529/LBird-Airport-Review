from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import httpx

from lbird.collectors.catalog_collector import parse_markdown_table
from lbird.http_client import PoliteHttpClient


async def discover_github_directories(
    discovery_cfg: dict[str, Any],
    http_client: PoliteHttpClient,
    known_repos: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Search public GitHub repositories for newly updated airport directory READMEs."""
    if not discovery_cfg or not discovery_cfg.get("enabled"):
        return []

    queries = discovery_cfg.get("queries") or []
    max_repos = max(1, min(5, int(discovery_cfg.get("max_repos_per_query") or 3)))
    known = {r.lower() for r in (known_repos or set())}

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": http_client.user_agent,
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    discovered: list[dict[str, Any]] = []
    seen_repos: set[str] = set()

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as api_client:
        for q in queries[:4]:
            url = f"https://api.github.com/search/repositories?q={quote(str(q))}&sort=updated&order=desc&per_page={max_repos}"
            try:
                resp = await api_client.get(url)
                if resp.status_code != 200:
                    continue
                items = resp.json().get("items") or []
            except Exception:
                continue

            for repo in items[:max_repos]:
                full_name = str(repo.get("full_name") or "").strip()
                branch = str(repo.get("default_branch") or "main").strip()
                if not full_name or full_name.lower() in known or full_name.lower() in seen_repos:
                    continue
                if "lbird-airport-review" in full_name.lower():
                    continue
                seen_repos.add(full_name.lower())

                raw_url = f"https://raw.githubusercontent.com/{full_name}/{branch}/README.md"
                md_resp = await http_client.get(raw_url, check_robots=False)
                if md_resp.ok and md_resp.text:
                    for item in parse_markdown_table(md_resp.text):
                        item.setdefault("tags", ["自动发现", "公开索引"])
                        discovered.append(item)

    return discovered
