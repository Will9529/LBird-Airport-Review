from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlparse

import yaml


SUPPORTED_SCHEMES = (
    "ss://",
    "ssr://",
    "vmess://",
    "vless://",
    "trojan://",
    "hy2://",
    "hysteria2://",
    "tuic://",
    "wireguard://",
)

REGION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("香港", re.compile(r"(🇭🇰|\bHK\b|Hong\s*Kong|香港)", re.I)),
    ("日本", re.compile(r"(🇯🇵|\bJP\b|Japan|Tokyo|Osaka|日本|东京|大阪)", re.I)),
    ("新加坡", re.compile(r"(🇸🇬|\bSG\b|Singapore|狮城|新加坡)", re.I)),
    ("美国", re.compile(r"(🇺🇸|\bUS\b|\bUSA\b|United\s*States|Los\s*Angeles|San\s*Jose|Seattle|New\s*York|美国|洛杉矶|圣何塞)", re.I)),
    ("台湾", re.compile(r"(🇹🇼|\bTW\b|Taiwan|Taipei|台湾|台北)", re.I)),
    ("韩国", re.compile(r"(🇰🇷|\bKR\b|Korea|Seoul|韩国|首尔)", re.I)),
    ("英国", re.compile(r"(🇬🇧|\bUK\b|\bGB\b|United\s*Kingdom|London|英国|伦敦)", re.I)),
    ("德国", re.compile(r"(🇩🇪|\bDE\b|Germany|Frankfurt|德国|法兰克福)", re.I)),
]

ROUTE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("IEPL", re.compile(r"\bIEPL\b", re.I)),
    ("IPLC", re.compile(r"\bIPLC\b", re.I)),
    ("CN2", re.compile(r"(CN2|GIA)", re.I)),
    ("BGP", re.compile(r"\bBGP\b", re.I)),
    ("中转", re.compile(r"(中转|Relay|Transit)", re.I)),
]


@dataclass(frozen=True)
class ParsedNode:
    """In-memory node endpoint for probing only; never persisted to public JSON."""

    name: str
    protocol: str
    host: str
    port: int


def _decode_b64(text: str) -> str:
    cleaned = "".join(text.strip().split())
    if not cleaned:
        return ""
    padded = cleaned + "=" * (-len(cleaned) % 4)
    for fn in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            raw = fn(padded)
            decoded = raw.decode("utf-8", errors="ignore")
            if any(s in decoded for s in SUPPORTED_SCHEMES) or "proxies:" in decoded:
                return decoded
        except Exception:
            continue
    return ""


def _parse_vmess_uri(uri: str) -> ParsedNode | None:
    payload = uri[len("vmess://") :].split("#", 1)[0].strip()
    padded = payload + "=" * (-len(payload) % 4)
    for fn in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            obj = json.loads(fn(padded).decode("utf-8"))
            host = str(obj.get("add") or "").strip()
            port = int(obj.get("port") or 0)
            name = str(obj.get("ps") or host).strip()
            if host and 1 <= port <= 65535:
                return ParsedNode(name=name, protocol="vmess", host=host, port=port)
        except Exception:
            continue
    return None


def _parse_standard_uri(uri: str) -> ParsedNode | None:
    scheme = uri.split("://", 1)[0].lower()
    if scheme == "vmess":
        return _parse_vmess_uri(uri)
    if scheme == "ssr":
        decoded = _decode_b64(uri[len("ssr://") :])
        if ":" in decoded:
            parts = decoded.split(":")
            if len(parts) >= 2 and parts[1].isdigit():
                return ParsedNode(name="ssr", protocol="ssr", host=parts[0], port=int(parts[1]))
        return None
    try:
        parsed = urlparse(uri)
        host = (parsed.hostname or "").strip()
        port = parsed.port
        if not host or not port or not (1 <= port <= 65535):
            return None
        name = unquote(parsed.fragment or host).strip()
        proto = "hysteria2" if scheme in ("hy2", "hysteria2") else scheme
        return ParsedNode(name=name, protocol=proto, host=host, port=int(port))
    except Exception:
        return None


def _parse_clash_yaml(raw_text: str) -> list[ParsedNode]:
    try:
        doc = yaml.safe_load(raw_text)
    except Exception:
        return []
    if not isinstance(doc, dict):
        return []
    proxies = doc.get("proxies")
    if not isinstance(proxies, list):
        return []
    nodes: list[ParsedNode] = []
    for item in proxies:
        if not isinstance(item, dict):
            continue
        host = str(item.get("server") or "").strip()
        try:
            port = int(item.get("port") or 0)
        except Exception:
            continue
        proto = str(item.get("type") or "unknown").strip().lower()
        name = str(item.get("name") or host).strip()
        if host and 1 <= port <= 65535:
            nodes.append(ParsedNode(name=name, protocol=proto, host=host, port=port))
    return nodes


def parse_subscription_text(raw_text: str) -> list[ParsedNode]:
    """Parse Clash YAML, Base64 URI lists, or plain URI lists into deduplicated ParsedNodes."""
    text = (raw_text or "").strip()
    if not text:
        return []

    nodes: list[ParsedNode] = []
    if "proxies:" in text:
        nodes = _parse_clash_yaml(text)

    if not nodes:
        candidate = text
        if not any(s in text for s in SUPPORTED_SCHEMES):
            decoded = _decode_b64(text)
            if decoded:
                if "proxies:" in decoded:
                    nodes = _parse_clash_yaml(decoded)
                else:
                    candidate = decoded
        if not nodes:
            for line in candidate.splitlines():
                line = line.strip()
                if not line or not line.startswith(SUPPORTED_SCHEMES):
                    continue
                node = _parse_standard_uri(line)
                if node:
                    nodes.append(node)

    seen: set[tuple[str, str, int]] = set()
    unique: list[ParsedNode] = []
    for n in nodes:
        key = (n.protocol, n.host.lower(), n.port)
        if key not in seen:
            seen.add(key)
            unique.append(n)
    return unique


def summarize_nodes(nodes: list[ParsedNode]) -> dict[str, Any]:
    """Extract strictly anonymized aggregate statistics (zero hosts/ports/credentials)."""
    regions: list[str] = []
    routes: list[str] = []
    protocols: dict[str, int] = {}

    for n in nodes:
        protocols[n.protocol] = protocols.get(n.protocol, 0) + 1
        for region_name, pat in REGION_PATTERNS:
            if region_name not in regions and pat.search(n.name):
                regions.append(region_name)
        for route_name, pat in ROUTE_PATTERNS:
            if route_name not in routes and pat.search(n.name):
                routes.append(route_name)

    return {
        "node_count": len(nodes),
        "regions": regions,
        "routes": routes,
        "protocols": sorted(protocols.keys()),
        "protocol_counts": protocols,
    }
