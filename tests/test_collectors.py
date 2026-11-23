from datetime import datetime, timezone

from lbird.collectors.catalog_collector import make_slug, parse_everett_jsonc, parse_jichangyyds_markdown, sanitize_website_url
from lbird.collectors.news_collector import parse_feed_xml
from lbird.collectors.risk_feed_collector import parse_jichangx_markdown
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


def test_slug_and_url_sanitization():
    assert make_slug("Forest") == "forest"
    assert make_slug("青风云网").startswith("ap-")
    assert sanitize_website_url("https://go.uukk.de/forest") == "#"
    assert sanitize_website_url("https://www.jichangyyds.com/brands/edgenova/") == "#"
    assert sanitize_website_url("https://example.org/panel?aff=123&lang=zh") == "https://example.org/panel?lang=zh"


def test_parse_jichangyyds_markdown_and_ratings():
    md = """
| 机场品牌 | 最低月付 | 优惠码 | 券后 | 编辑评分 | 节点数 |
| --- | ---: | --- | ---: | ---: | ---: |
| [测试云](https://www.jichangyyds.com/brands/ceshi/) | ¥18 | `TEST88` | ¥15.84 | 4.2 | 45 |

| 机场品牌 | 可用/总节点 | 香港中位速度 | 香港中位延迟 | 测试入口 | 数据来源 |
| --- | ---: | ---: | ---: | --- | --- |
| [测试云](https://www.jichangyyds.com/brands/ceshi/) | 44/45 | 80.0 MB/s | 42 ms | A | 本站实测 |

| # | 机场品牌 | 套餐 | 流量 | 价格 | 每 GB |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | [测试云](https://www.jichangyyds.com/brands/ceshi/) | 标准版 | 200GB | ¥18/月 | ¥0.09 |
"""
    entries, deals = parse_jichangyyds_markdown(md)
    assert len(entries) == 1
    e = entries[0]
    assert e["nodes"] == 45
    assert e["externalRating"] == 4.2
    assert e["benchSpeedMbps"] == 640.0
    assert e["benchLatencyMs"] == 42.0
    assert e["benchUptime"] == 97.78
    assert len(e["plans"]) == 1
    assert len(deals) == 1 and deals[0]["code"] == "TEST88"


def test_parse_everett_jsonc_and_jichangx_risk():
    jsonc = """// comment line
    {
      "no_aff": [
        {"name": "AmyTelecom", "url": "https://go.uukk.de/amytele", "coupon": "SAVE10", "lineType": "IEPL专线", "pricing": "¥240/年起", "tags": ["稳定"]}
      ],
      "defunct": [
        {"name": "DeadNet", "defunctDate": "2026-11-18", "lineType": "中转", "pricingWas": "¥9.9/月"}
      ]
    }"""
    entries, deals = parse_everett_jsonc(jsonc)
    assert len(entries) == 2
    assert entries[0]["priceMonthly"] == 20.0
    assert entries[0]["website"] == "#"
    assert entries[1]["is_risk_entry"] is True
    assert len(deals) == 1 and deals[0]["code"] == "SAVE10"

    risk_md = """| 名字 | 类型 | 警告级别 | 年份 | 最后更新 | 来源 |
| ---- | ---- | ---- | ---- | ---- | ---- |
| ~~快帆云~~ | 机场 | 跑路 | 2025 | 02.26.2024 | [反馈](https://github.com/x) |"""
    r_map, r_entries = parse_jichangx_markdown(risk_md)
    assert len(r_entries) == 1
    assert r_entries[0]["name"] == "快帆云"
    assert "跑路" in r_map[r_entries[0]["slug"]]
