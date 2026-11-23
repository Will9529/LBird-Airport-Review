from __future__ import annotations

import asyncio
import json
import os
import shutil
import statistics
import subprocess
import tempfile
import time
from typing import Any

from lbird.http_client import PoliteHttpClient, is_safe_ip_literal
from lbird.models import SubProbeResult
from lbird.parsers.sub_parser import ParsedNode, parse_subscription_text, summarize_nodes


def load_secret_subscriptions() -> dict[str, str]:
    raw = os.environ.get("LBIRD_SUBSCRIPTIONS_JSON", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k).strip().lower(): str(v).strip() for k, v in parsed.items() if k and v}
    except Exception:
        pass
    return {}


async def _tcp_probe_one(node: ParsedNode, timeout_sec: float) -> float | None:
    if not is_safe_ip_literal(node.host):
        return None
    t0 = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(node.host, node.port),
            timeout=timeout_sec,
        )
        rtt_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return rtt_ms
    except Exception:
        return None


def _run_optional_cli_speedtest(raw_text: str) -> float | None:
    binary = shutil.which("clash-speedtest")
    if not binary or "proxies:" not in raw_text:
        return None
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as fp:
            fp.write(raw_text)
            tmp_path = fp.name
        proc = subprocess.run(
            [binary, "-c", tmp_path, "-output", "json"],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout:
            data = json.loads(proc.stdout)
            if isinstance(data, list) and data:
                speeds = [float(x.get("speed_mbps", 0)) for x in data if float(x.get("speed_mbps", 0)) > 0]
                if speeds:
                    return round(statistics.median(speeds), 2)
    except Exception:
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    return None


async def probe_subscription(
    slug: str,
    sub_url: str,
    http_client: PoliteHttpClient,
    sample_size: int = 16,
    tcp_timeout_sec: float = 4.0,
    enable_cli_speedtest: bool = False,
) -> SubProbeResult:
    if not sub_url:
        return SubProbeResult()

    resp = await http_client.get(sub_url, check_robots=False)
    if not resp.ok or not resp.text:
        return SubProbeResult(probed=True, mode="tcp_passive", error=resp.error or "empty_subscription")

    nodes = parse_subscription_text(resp.text)
    if not nodes:
        return SubProbeResult(probed=True, mode="tcp_passive", error="no_nodes_parsed")

    agg = summarize_nodes(nodes)
    # Sample evenly across parsed nodes for bounded, fast TCP handshake verification
    step = max(1, len(nodes) // max(1, sample_size))
    sample = nodes[::step][:sample_size]

    sem = asyncio.Semaphore(8)

    async def _bounded(n: ParsedNode) -> float | None:
        async with sem:
            return await _tcp_probe_one(n, tcp_timeout_sec)

    rtts = await asyncio.gather(*(_bounded(n) for n in sample))
    ok_rtts = [r for r in rtts if r is not None]

    sample_n = len(sample)
    ok_n = len(ok_rtts)
    uptime_pct = round((ok_n / sample_n) * 100.0, 2) if sample_n else 0.0
    loss_pct = round(100.0 - uptime_pct, 2)
    latency_ms = round(statistics.median(ok_rtts), 2) if ok_rtts else None

    speed_mbps: float | None = None
    mode = "tcp_passive"
    if enable_cli_speedtest:
        speed_mbps = await asyncio.to_thread(_run_optional_cli_speedtest, resp.text)
        if speed_mbps is not None:
            mode = "speedtest"

    return SubProbeResult(
        probed=True,
        mode=mode,
        node_count=agg["node_count"],
        sample_count=sample_n,
        reachable_count=ok_n,
        uptime_pct=uptime_pct,
        latency_ms=latency_ms,
        loss_pct=loss_pct,
        speed_mbps=speed_mbps,
        regions=agg["regions"],
        routes=agg["routes"],
        protocols=agg["protocols"],
    )
