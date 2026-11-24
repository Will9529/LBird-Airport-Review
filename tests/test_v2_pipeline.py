from __future__ import annotations

from datetime import datetime, timezone

from lbird.collectors.catalog_collector import parse_qweqwe_csv
from lbird.collectors.news_collector import parse_feed_xml
from lbird.collectors.official_resolver import is_valid_resolved_origin, normalize_cache_key
from lbird.models import SubProbeResult, TelegramResult, WebHealthResult
from lbird.scoring import evaluate_target


def test_official_resolver_filters_competitors_and_private():
    assert is_valid_resolved_origin("https://example-airport.com/") is True
    assert is_valid_resolved_origin("https://jichangyyds.com/") is False
    assert is_valid_resolved_origin("https://go.uukk.de/") is False
    assert is_valid_resolved_origin("https://github.com/foo/bar") is False
    assert is_valid_resolved_origin("http://127.0.0.1:8000/") is False
    assert normalize_cache_key("Fly (飞鸟)") == "fly飞鸟"


def test_waf_protected_does_not_trigger_risk_and_records_slots():
    entry = {"slug": "cf-test", "name": "CFTest", "website": "https://cf-test.example.org", "priceMonthly": 15.0}
    web = WebHealthResult(
        url="https://cf-test.example.org",
        ok=False,
        http_status=403,
        ttfb_ms=120.0,
        blocked=True,
        waf_protected=True,
        dns_ok=True,
        tls_ok=True,
    )
    t_normal = datetime(2026, 11, 25, 6, 0, tzinfo=timezone.utc)  # 14:00 CST
    rec1, st1 = evaluate_target(entry, web, TelegramResult(), SubProbeResult(), "", {}, now=t_normal)
    assert rec1["status"] == "normal"
    assert rec1["dataTier"] == "web_monitored"
    assert rec1["probeMeta"]["healthStatus"] == "waf_protected"
    assert rec1["historyPoints"] == 1
    assert "未测(数据中心IP)" not in rec1["streaming"]

    t_peak = datetime(2026, 11, 25, 13, 0, tzinfo=timezone.utc)  # 21:00 CST
    rec2, st2 = evaluate_target(entry, web, TelegramResult(), SubProbeResult(), "", st1, now=t_peak)
    assert rec2["historyPoints"] == 2
    assert [s["slot"] for s in rec2["slotHistory"]] == ["normal", "peak"]


def test_qweqwe_csv_parser():
    csv_txt = "brand,brand_slug,tested_at_cst,tool,tool_version,nodes_declared,nodes_in_table,sort_order,protocol_observed,review_url,data_note\n飞猫云,feimaoyun,2026-08-05 17:24,喵酷 MiaoKo,4.7.0,50,50,HTTP 延迟降序,VLESS,https://example.org,note1\n"
    parsed = parse_qweqwe_csv(csv_txt)
    assert "飞猫云" in parsed
    assert parsed["飞猫云"]["nodesObserved"] == 50
    assert parsed["飞猫云"]["protocolObserved"] == "VLESS"


def test_news_filters_prerelease_and_prefixes_title():
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Prerelease-Alpha</title>
        <updated>2026-11-24T00:00:00Z</updated>
        <link href="https://github.com/2dust/v2rayN/releases/tag/alpha"/>
        <content>alpha build</content>
      </entry>
      <entry>
        <title>8.0.1</title>
        <updated>2026-11-24T00:00:00Z</updated>
        <link href="https://github.com/2dust/v2rayN/releases/tag/8.0.1"/>
        <content>&lt;p&gt;Fix TUN DNS leak.&lt;/p&gt;</content>
      </entry>
    </feed>"""
    recs = parse_feed_xml(xml, "客户端更新", project_name="v2rayN")
    assert len(recs) == 1
    assert recs[0].title == "v2rayN 8.0.1"
    assert "Fix TUN DNS leak." in recs[0].content
