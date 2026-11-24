from __future__ import annotations

import asyncio
import ssl
from datetime import datetime, timezone
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from lbird.http_client import PoliteHttpClient, is_safe_public_url
from lbird.models import WebHealthResult


CLIENT_HINTS = ["Clash Verge", "Mihomo", "v2rayN", "Shadowrocket", "Karing", "Stash", "Sing-box"]
ROUTE_HINTS = ["IEPL", "IPLC", "CN2", "BGP", "中转"]
PAYMENT_HINTS = ["支付宝", "微信", "USDT"]


def _inspect_tls_sync(host: str, port: int = 443, timeout: float = 5.0) -> tuple[bool, int | None]:
    ctx = ssl.create_default_context()
    try:
        with ctx.wrap_socket(
            __import__("socket").create_connection((host, port), timeout=timeout),
            server_hostname=host,
        ) as sock:
            cert = sock.getpeercert()
            if not cert:
                return True, None
            not_after = cert.get("notAfter")
            if not not_after:
                return True, None
            dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            days_left = (dt - datetime.now(timezone.utc)).days
            return days_left >= 0, days_left
    except Exception:
        return False, None


async def _check_dns(host: str) -> bool:
    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(loop.getaddrinfo(host, None), timeout=4.0)
        return bool(infos)
    except Exception:
        return False


def _extract_html_hints(html: str, res: WebHealthResult) -> None:
    if not html:
        return
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        res.title = " ".join(soup.title.string.split())[:120]
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        res.description = " ".join(str(meta_desc.get("content")).split())[:220]

    text = soup.get_text(" ", strip=True)
    lower = text.lower()
    res.detected_clients = [c for c in CLIENT_HINTS if c.lower() in lower]
    res.detected_routes = [r for r in ROUTE_HINTS if r.lower() in lower]
    res.detected_payments = [p for p in PAYMENT_HINTS if p.lower() in lower]
    res.detected_trial = any(k in lower for k in ("试用", "free trial", "免费体验"))
    res.detected_refund = any(k in lower for k in ("退款", "refund"))


async def probe_website(url: str, http_client: PoliteHttpClient) -> WebHealthResult:
    res = WebHealthResult(url=url)
    if not url or not is_safe_public_url(url):
        res.error = "invalid_or_unsafe_url"
        return res

    parsed = urlparse(url)
    host = (parsed.hostname or "").strip()
    if not host:
        res.error = "missing_host"
        return res

    res.dns_ok = await _check_dns(host)
    if not res.dns_ok:
        res.error = "dns_failed"
        return res

    if parsed.scheme == "https":
        port = parsed.port or 443
        tls_ok, days_left = await asyncio.to_thread(_inspect_tls_sync, host, port)
        res.tls_ok = tls_ok
        res.tls_days_left = days_left

    resp = await http_client.get(url, check_robots=True)
    res.http_status = resp.status_code
    res.ttfb_ms = resp.ttfb_ms
    res.blocked = resp.blocked
    res.waf_protected = resp.waf_protected
    res.final_url = resp.final_url or url
    res.ok = resp.ok
    res.error = resp.error
    if resp.text:
        _extract_html_hints(resp.text, res)

    # Lightweight V2Board / Xboard guest config probe (never fails main health check)
    if res.ok or res.waf_protected:
        try:
            origin = f"{parsed.scheme}://{parsed.netloc}"
            cfg_resp = await asyncio.wait_for(
                http_client.get(f"{origin}/api/v1/guest/comm/config", check_robots=False, max_retries=0),
                timeout=4.5,
            )
            if cfg_resp.ok and cfg_resp.text and cfg_resp.text.lstrip().startswith("{"):
                import json

                cfg_json = json.loads(cfg_resp.text)
                if isinstance(cfg_json, dict) and isinstance(cfg_json.get("data"), dict):
                    res.panel_type = "v2board"
                    data_obj = cfg_json["data"]
                    if data_obj.get("is_trial_enable") or data_obj.get("try_out_plan_id"):
                        res.detected_trial = True
        except Exception:
            pass

    return res
