from __future__ import annotations

import asyncio
import ipaddress
import time
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx


BLOCK_MARKERS = (
    "cf-turnstile",
    "g-recaptcha",
    "h-captcha",
    "just a moment...",
    "attention required! | cloudflare",
    "verify you are human",
)


def is_safe_public_url(url: str) -> bool:
    """Reject non-HTTP(S) schemes and loopback/private/link-local/metadata hosts (SSRF guard)."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host or host in ("localhost", "ip6-localhost"):
        return False
    if host.endswith(".local") or host.endswith(".internal"):
        return False
    try:
        ip = ipaddress.ip_address(host)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    except ValueError:
        pass
    return True


def is_safe_ip_literal(host: str) -> bool:
    """Check if a raw IP host (if IP literal) is safe to probe."""
    h = host.strip().strip("[]")
    if not h or h.lower() in ("localhost", "ip6-localhost"):
        return False
    try:
        ip = ipaddress.ip_address(h)
        return not (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return True


@dataclass
class HttpResponseData:
    ok: bool
    status_code: int | None
    text: str = ""
    final_url: str = ""
    ttfb_ms: float | None = None
    blocked: bool = False
    waf_protected: bool = False
    error: str = ""


class PoliteHttpClient:
    """Async HTTP client enforcing SSRF checks, per-domain rate limits, and robots.txt."""

    def __init__(
        self,
        user_agent: str,
        timeout_sec: float = 12.0,
        per_domain_delay_sec: float = 0.8,
        respect_robots_txt: bool = True,
    ) -> None:
        self.user_agent = user_agent
        self.timeout_sec = timeout_sec
        self.per_domain_delay_sec = per_domain_delay_sec
        self.respect_robots_txt = respect_robots_txt
        self._domain_locks: dict[str, asyncio.Lock] = {}
        self._domain_last_ts: dict[str, float] = {}
        self._robots_cache: dict[str, RobotFileParser | None] = {}
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_sec),
            follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"},
        )

    async def __aenter__(self) -> "PoliteHttpClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _throttle(self, host: str) -> None:
        lock = self._domain_locks.setdefault(host, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            last = self._domain_last_ts.get(host, 0.0)
            wait = self.per_domain_delay_sec - (now - last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._domain_last_ts[host] = time.monotonic()

    async def _check_robots(self, url: str) -> bool:
        if not self.respect_robots_txt:
            return True
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots_cache:
            robots_url = f"{origin}/robots.txt"
            rp = RobotFileParser()
            try:
                resp = await self._client.get(robots_url, timeout=5.0)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                    self._robots_cache[origin] = rp
                else:
                    self._robots_cache[origin] = None
            except Exception:
                self._robots_cache[origin] = None
        cached = self._robots_cache.get(origin)
        if cached is None:
            return True
        return cached.can_fetch(self.user_agent, url)

    async def get(self, url: str, check_robots: bool = True, max_retries: int = 1) -> HttpResponseData:
        if not is_safe_public_url(url):
            return HttpResponseData(ok=False, status_code=None, error="unsafe_or_private_url")

        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        if check_robots and not await self._check_robots(url):
            return HttpResponseData(ok=False, status_code=None, error="disallowed_by_robots_txt")

        last_err = ""
        for attempt in range(max_retries + 1):
            await self._throttle(host)
            t0 = time.perf_counter()
            try:
                resp = await self._client.get(url)
                elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                if not is_safe_public_url(str(resp.url)):
                    return HttpResponseData(ok=False, status_code=resp.status_code, error="unsafe_redirect_target")
                body = resp.text or ""
                lowered = body[:4096].lower()
                blocked = any(marker in lowered for marker in BLOCK_MARKERS)
                hdrs = {k.lower(): v for k, v in resp.headers.items()}
                is_cf_waf = bool(
                    hdrs.get("cf-mitigated")
                    or (hdrs.get("cf-ray") and (resp.status_code in (403, 503) or blocked))
                    or ("cloudflare" in hdrs.get("server", "").lower() and resp.status_code in (403, 503) and blocked)
                )
                if resp.status_code in (401, 403, 404, 429):
                    return HttpResponseData(
                        ok=False,
                        status_code=resp.status_code,
                        text=body,
                        final_url=str(resp.url),
                        ttfb_ms=elapsed_ms,
                        blocked=blocked or resp.status_code in (403, 429),
                        waf_protected=is_cf_waf,
                        error=f"http_{resp.status_code}",
                    )
                if resp.status_code >= 500 and attempt < max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                ok = 200 <= resp.status_code < 400 and not blocked
                return HttpResponseData(
                    ok=ok,
                    status_code=resp.status_code,
                    text=body,
                    final_url=str(resp.url),
                    ttfb_ms=elapsed_ms,
                    blocked=blocked,
                    waf_protected=is_cf_waf,
                    error="" if ok else ("challenge_blocked" if blocked else f"http_{resp.status_code}"),
                )
            except Exception as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
        return HttpResponseData(ok=False, status_code=None, error=last_err)
