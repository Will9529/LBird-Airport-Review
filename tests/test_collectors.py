from datetime import datetime, timezone

from lbird.collectors.news_collector import parse_feed_xml
from lbird.collectors.telegram_collector import parse_telegram_preview_html
from lbird.http_client import is_safe_public_url


def test_ssrf_guard_blocks_private_and_metadata_urls():
    assert is_safe_public_url("https://github.com/Will9529")
    assert not is_safe_public_url("http://127.0.0.1:8080/admin")
    assert not is_safe_public_url("http://169.254.169.254/latest/meta-data/")
    assert not is_safe_public_url("http://10.0.0.5/internal")
    assert not is_safe_public_url("file:///etc/passwd")
    assert not is_safe_public_url("http://localhost:3000")


def test_telegram_preview_coupon_and_activity_extraction():
    html = """
    <div class="tgme_widget_message">
      <time datetime="2026-11-20T10:00:00+00:00"></time>
      <div class="tgme_widget_message_text">双十一活动开启，优惠码: BIRD88，全场 88 折！</div>
    </div>
    <div class="tgme_widget_message">
      <time datetime="2026-11-23T12:00:00+00:00"></time>
      <div class="tgme_widget_message_text">昨晚香港节点短暂维护，现已恢复。</div>
    </div>
    """
    now = datetime(2026, 11, 24, 0, 0, tzinfo=timezone.utc)
    res = parse_telegram_preview_html(html, "test_chan", "test-slug", now=now)
    assert res.reachable is True
    assert res.last_post_days_ago == 0
    assert res.outage_mentions == 1
    assert len(res.deals) == 1
    assert res.deals[0]["code"] == "BIRD88"
    assert res.deals[0]["airportSlug"] == "test-slug"


def test_atom_news_parser():
    atom = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>v1.19.0</title>
        <updated>2026-11-22T08:00:00Z</updated>
        <link href="https://github.com/MetaCubeX/mihomo/releases/tag/v1.19.0" />
        <content type="html">&lt;p&gt;Fix DNS leak and improve performance.&lt;/p&gt;</content>
      </entry>
    </feed>
    """
    items = parse_feed_xml(atom, "内核动态")
    assert len(items) == 1
    assert items[0].date == "2026/11/22"
    assert items[0].category == "内核动态"
    assert "Fix DNS leak" in items[0].summary
