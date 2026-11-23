from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from lbird.http_client import PoliteHttpClient
from lbird.models import TelegramResult


COUPON_RE = re.compile(
    r"(?:优惠码|折扣码|coupon|promo(?:\s*code)?)\s*[:：]?\s*`?([A-Z0-9_-]{4,20})`?",
    re.I,
)
DISCOUNT_RE = re.compile(r"(\d+(?:\.\d+)?\s*折|\d+%\s*off|立减\s*\d+)", re.I)
OUTAGE_KEYWORDS = ("维护", "波动", "故障", "停服", "失联", "被墙", "迁移")


def parse_telegram_preview_html(html: str, channel: str, airport_slug: str, now: datetime | None = None) -> TelegramResult:
    now = now or datetime.now(timezone.utc)
    res = TelegramResult(channel=channel, reachable=bool(html))
    if not html:
        return res

    soup = BeautifulSoup(html, "html.parser")
    msgs = soup.select(".tgme_widget_message")
    if not msgs:
        return res

    latest_dt: datetime | None = None
    seen_codes: set[str] = set()

    for msg in msgs[-15:]:
        time_el = msg.select_one("time[datetime]")
        if time_el and time_el.get("datetime"):
            try:
                dt = datetime.fromisoformat(str(time_el["datetime"]).replace("Z", "+00:00"))
                if latest_dt is None or dt > latest_dt:
                    latest_dt = dt
            except Exception:
                pass

        text_el = msg.select_one(".tgme_widget_message_text")
        if not text_el:
            continue
        text = text_el.get_text(" ", strip=True)
        if any(k in text for k in OUTAGE_KEYWORDS):
            res.outage_mentions += 1

        m_code = COUPON_RE.search(text)
        if m_code:
            code = m_code.group(1).upper()
            if code not in seen_codes:
                seen_codes.add(code)
                m_disc = DISCOUNT_RE.search(text)
                discount = m_disc.group(1) if m_disc else "频道限时优惠"
                res.deals.append(
                    {
                        "airportSlug": airport_slug,
                        "code": code,
                        "discount": discount,
                        "plans": "详见频道公告",
                        "dateRange": now.strftime("%Y-%m-%d") + " 起",
                        "stackable": False,
                        "refundable": False,
                        "active": True,
                    }
                )

    if latest_dt is not None:
        res.last_post_days_ago = max(0, (now - latest_dt).days)
    return res


async def fetch_telegram_channel(channel: str, airport_slug: str, http_client: PoliteHttpClient) -> TelegramResult:
    clean = channel.strip().lstrip("@")
    if not clean or "/" in clean:
        return TelegramResult(channel=clean, reachable=False, error="invalid_channel")
    url = f"https://t.me/s/{clean}"
    resp = await http_client.get(url, check_robots=False)
    if not resp.ok:
        return TelegramResult(channel=clean, reachable=False, error=resp.error)
    return parse_telegram_preview_html(resp.text, clean, airport_slug)
