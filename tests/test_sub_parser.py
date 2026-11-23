import base64
import json

from lbird.parsers.sub_parser import parse_subscription_text, summarize_nodes


def test_parse_clash_yaml_dedup_and_sanitize():
    raw = """
proxies:
  - name: "🇭🇰 HK IEPL 01"
    type: vmess
    server: 203.0.113.10
    port: 443
    uuid: 11111111-1111-1111-1111-111111111111
  - name: "🇭🇰 HK IEPL 01 Dup"
    type: vmess
    server: 203.0.113.10
    port: 443
    uuid: 22222222-2222-2222-2222-222222222222
  - name: "🇯🇵 Tokyo CN2"
    type: trojan
    server: 198.51.100.20
    port: 8443
    password: super-secret-password
"""
    nodes = parse_subscription_text(raw)
    assert len(nodes) == 2
    summary = summarize_nodes(nodes)
    assert summary["node_count"] == 2
    assert "香港" in summary["regions"]
    assert "日本" in summary["regions"]
    assert "IEPL" in summary["routes"]
    assert "CN2" in summary["routes"]

    serialized = json.dumps(summary, ensure_ascii=False)
    assert "203.0.113.10" not in serialized
    assert "super-secret-password" not in serialized
    assert "11111111-1111-1111-1111-111111111111" not in serialized


def test_parse_base64_uris():
    vmess_obj = base64.b64encode(
        json.dumps({"add": "198.51.100.5", "port": 443, "ps": "🇸🇬 SG BGP"}).encode()
    ).decode()
    raw_uris = "\n".join(
        [
            f"vmess://{vmess_obj}",
            "trojan://secretpass@203.0.113.55:443#🇺🇸%20US%2001",
            "hysteria2://token@192.0.2.8:8443#🇹🇼%20TW%2001",
        ]
    )
    b64_sub = base64.b64encode(raw_uris.encode()).decode()
    nodes = parse_subscription_text(b64_sub)
    assert len(nodes) == 3
    summary = summarize_nodes(nodes)
    assert set(summary["regions"]) == {"新加坡", "美国", "台湾"}
    assert set(summary["protocols"]) == {"hysteria2", "trojan", "vmess"}
