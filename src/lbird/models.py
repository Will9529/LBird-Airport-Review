from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


CANONICAL_REGIONS = ["香港", "日本", "新加坡", "美国", "台湾", "韩国", "英国", "德国"]
CANONICAL_ROUTES = ["IEPL", "IPLC", "CN2", "BGP", "中转"]
CANONICAL_CLIENTS = ["Clash Verge", "Mihomo", "v2rayN", "Shadowrocket", "Karing", "Stash", "Sing-box"]


@dataclass
class WebHealthResult:
    url: str
    ok: bool = False
    http_status: int | None = None
    ttfb_ms: float | None = None
    blocked: bool = False
    waf_protected: bool = False
    panel_type: str = ""
    final_url: str = ""
    dns_ok: bool = False
    tls_ok: bool = False
    tls_days_left: int | None = None
    founded_rdap: str | None = None
    title: str = ""
    description: str = ""
    detected_clients: list[str] = field(default_factory=list)
    detected_routes: list[str] = field(default_factory=list)
    detected_payments: list[str] = field(default_factory=list)
    detected_trial: bool = False
    detected_refund: bool = False
    error: str = ""


@dataclass
class TelegramResult:
    channel: str = ""
    reachable: bool = False
    last_post_days_ago: int | None = None
    outage_mentions: int = 0
    deals: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""


@dataclass
class SubProbeResult:
    probed: bool = False
    mode: str = "none"  # none | tcp_passive | speedtest
    node_count: int = 0
    sample_count: int = 0
    reachable_count: int = 0
    uptime_pct: float | None = None
    latency_ms: float | None = None
    loss_pct: float | None = None
    speed_mbps: float | None = None
    regions: list[str] = field(default_factory=list)
    routes: list[str] = field(default_factory=list)
    protocols: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class DealRecord:
    airportSlug: str
    code: str
    discount: str
    plans: str = "全线套餐"
    dateRange: str = ""
    stackable: bool = False
    refundable: bool = False
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NewsRecord:
    id: str
    category: str
    title: str
    summary: str
    date: str
    url: str = ""
    content: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReportRecord:
    month: str
    year: str
    title: str
    sample: int
    top: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
