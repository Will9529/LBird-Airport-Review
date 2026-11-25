from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from lbird.models import ReportRecord, SubProbeResult, TelegramResult, WebHealthResult


def clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, val))


def compute_weighted_score(scores: dict[str, int]) -> float:
    val = (
        scores["S"] * 0.30
        + scores["P"] * 0.25
        + scores["N"] * 0.20
        + scores["C"] * 0.15
        + scores["R"] * 0.10
    )
    return round(val, 2)


def _pad_series(values: list[float], target_len: int = 30) -> list[float]:
    if not values:
        return [0.0, 0.0]
    if len(values) == 1:
        return [values[0], values[0]]
    return values[-target_len:]


def evaluate_target(
    entry: dict[str, Any],
    web: WebHealthResult,
    tg: TelegramResult,
    sub: SubProbeResult,
    risk_reason: str,
    prev_state: dict[str, Any],
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compute S-P-N-C-R scores, status, and rolling 30-day history."""
    now = now or datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    first_seen = prev_state.get("first_seen") or today
    try:
        d0 = datetime.strptime(first_seen, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        observed_days = max(1, (now - d0).days + 1)
    except Exception:
        observed_days = max(1, int(prev_state.get("observed_days") or 1))

    is_risk_entry = bool(entry.get("is_risk_entry"))
    is_directory_only = (str(entry.get("website") or "#").strip() == "#") and not sub.probed

    if is_risk_entry:
        scores = {"S": 28, "P": 28, "N": 32, "C": 48, "R": 18}
        total_score = compute_weighted_score(scores)
        uptime_pct = 0.0
        latency_ms = 420.0
        loss_pct = 100.0
        speed_mbps = 5.0
        consecutive_failures = max(3, int(prev_state.get("consecutive_failures") or 0) + 1)
        status = "risk"
        regions = list(entry.get("regions") or ["香港", "日本", "新加坡"])
        routes = list(entry.get("routes") or ["中转"])
        clients = list(entry.get("clients") or ["Clash Verge", "v2rayN"])
        payments = list(entry.get("payments") or ["未知"])
        nodes_count = int(entry.get("nodes") or 8)
        summary = str(entry.get("summary") or risk_reason or "社区公开风险清单记录：疑似跑路或停止服务。")
        probe_mode = "risk_feed"
    elif is_directory_only:
        price = float(entry.get("priceMonthly") if entry.get("priceMonthly") is not None else 15.0)
        nodes_count = int(entry.get("nodes") or 0)
        ext_rating = entry.get("externalRating")
        has_bench = any(k in entry for k in ("benchSpeedMbps", "benchLatencyMs", "benchUptime"))

        uptime_pct = float(entry.get("benchUptime") or (96.0 if has_bench else 92.0))
        latency_ms = float(entry.get("benchLatencyMs") or 85.0)
        speed_mbps = float(entry.get("benchSpeedMbps") or 120.0)
        loss_pct = round(max(0.0, 100.0 - uptime_pct), 2) if has_bench else 1.2

        # Differentiate S/P/N/C/R using real parsed benchmark metrics + external ratings when available
        if ext_rating is not None:
            base_s = 58.0 + float(ext_rating) * 7.5
        else:
            base_s = 74.0
        if has_bench:
            base_s = max(base_s, uptime_pct * 0.94)
        score_s = int(round(clamp(base_s, 45.0, 96.0)))

        if "benchSpeedMbps" in entry:
            p_raw = 52.0 + min(45.0, speed_mbps / 15.0)
        elif ext_rating is not None:
            p_raw = 55.0 + float(ext_rating) * 6.5
        else:
            p_raw = 72.0
        score_p = int(round(clamp(p_raw, 45.0, 96.0)))

        if "benchLatencyMs" in entry:
            n_raw = 94.0 - max(0.0, (latency_ms - 35.0) / 4.5)
        elif nodes_count > 0:
            n_raw = 70.0 + min(18.0, nodes_count / 5.0)
        else:
            n_raw = 74.0
        score_n = int(round(clamp(n_raw, 45.0, 96.0)))

        c_raw = 95.0 if price <= 0 else (104.0 - price * 1.05)
        if entry.get("trial"):
            c_raw += 4.0
        if entry.get("refund"):
            c_raw += 3.0
        score_c = int(round(clamp(c_raw, 45.0, 98.0)))

        r_raw = 35.0 if risk_reason else (72.0 + (float(ext_rating) * 3.0 if ext_rating is not None else 2.0))
        score_r = int(round(clamp(r_raw)))

        scores = {"S": score_s, "P": score_p, "N": score_n, "C": score_c, "R": score_r}
        total_score = compute_weighted_score(scores)
        if risk_reason:
            uptime_pct = 30.0
            loss_pct = 35.0
            speed_mbps = 20.0
        consecutive_failures = 0 if not risk_reason else 3
        status = "risk" if risk_reason else "normal"
        regions = list(entry.get("regions") or ["香港", "日本", "新加坡", "美国"])
        routes = list(entry.get("routes") or ["BGP"])
        clients = list(entry.get("clients") or ["Clash Verge", "Mihomo", "v2rayN"])
        payments = list(entry.get("payments") or ["支付宝", "USDT"])
        summary = risk_reason or str(entry.get("summary") or "公开目录收录观测中。")
        probe_mode = "directory_bench" if has_bench else "directory_index"
    else:
        # Determine probe reachability for consecutive failure streak (CF WAF counts as alive)
        website_str = str(entry.get("website") or "#")
        waf_alive = bool(web.dns_ok and web.waf_protected and (web.tls_ok or not website_str.startswith("https://")))
        probe_ok = web.ok or waf_alive or (sub.probed and (sub.uptime_pct or 0) >= 30.0)
        prev_failures = int(prev_state.get("consecutive_failures") or 0)
        consecutive_failures = 0 if probe_ok else prev_failures + 1

        # Snapshot metrics
        if sub.probed and sub.uptime_pct is not None:
            uptime_pct = sub.uptime_pct
        else:
            uptime_pct = 99.0 if web.ok else (96.0 if waf_alive else (70.0 if web.blocked else 15.0))

        latency_ms = sub.latency_ms if (sub.probed and sub.latency_ms is not None) else (web.ttfb_ms or 280.0)
        loss_pct = sub.loss_pct if (sub.probed and sub.loss_pct is not None) else (0.5 if (web.ok or waf_alive) else 35.0)

        if sub.speed_mbps is not None:
            speed_mbps = sub.speed_mbps
        else:
            # Conservative passive throughput proxy derived from handshake RTT & availability
            speed_mbps = round(max(12.0, min(260.0, 280.0 - latency_ms * 0.45)) * (uptime_pct / 100.0), 1)

        # S: Stability (30%)
        s_raw = (uptime_pct * 0.72) + (28.0 if web.ok else (22.0 if waf_alive else (16.0 if web.blocked else 4.0)))
        if sub.probed and sub.node_count >= 10 and (sub.uptime_pct or 0) >= 60:
            s_raw = max(s_raw, uptime_pct * 0.92)
        score_s = int(round(clamp(s_raw)))

        # P: Performance (25%)
        if sub.speed_mbps is not None:
            p_raw = 40.0 + min(60.0, sub.speed_mbps / 6.0)
        else:
            # Passive cap at 88 so passive probes never claim 100 without real throughput tests
            p_raw = min(88.0, 42.0 + max(0.0, 46.0 - (latency_ms / 12.0))) * (0.5 + 0.5 * (uptime_pct / 100.0))
        score_p = int(round(clamp(p_raw)))

        # N: Network (20%)
        lat_penalty = max(0.0, (latency_ms - 40.0) / 8.0)
        loss_penalty = loss_pct * 0.8
        regions = sub.regions or list(entry.get("regions") or ["香港", "日本", "新加坡"])
        breadth_bonus = min(10.0, len(regions) * 1.5)
        score_n = int(round(clamp(92.0 - lat_penalty - loss_penalty + breadth_bonus - 6.0)))

        # C: Cost (15%)
        price = float(entry.get("priceMonthly") if entry.get("priceMonthly") is not None else 15.0)
        if price <= 0:
            c_raw = 95.0
        else:
            c_raw = 104.0 - price * 1.05
        if entry.get("trial") or web.detected_trial:
            c_raw += 4.0
        if entry.get("refund") or web.detected_refund:
            c_raw += 3.0
        score_c = int(round(clamp(c_raw, 45.0, 98.0)))

        # R: Risk (10%)
        r_raw = 88.0
        if not web.dns_ok:
            r_raw -= 30.0
        if not web.tls_ok and str(entry.get("website", "")).startswith("https://"):
            r_raw -= 15.0
        if web.tls_days_left is not None and web.tls_days_left < 7:
            r_raw -= 10.0
        if not web.ok and not web.blocked and not waf_alive:
            r_raw -= 18.0
        r_raw -= consecutive_failures * 18.0
        if risk_reason:
            r_raw -= 45.0
        if observed_days >= 30 and consecutive_failures == 0:
            r_raw += 6.0
        score_r = int(round(clamp(r_raw)))

        scores = {"S": score_s, "P": score_p, "N": score_n, "C": score_c, "R": score_r}
        total_score = compute_weighted_score(scores)

        if risk_reason or consecutive_failures >= 3 or score_r < 40 or uptime_pct < 50:
            status = "risk"
        elif consecutive_failures >= 1 or score_r < 65 or uptime_pct < 80:
            status = "watch"
        else:
            status = "normal"

        routes = list(dict.fromkeys((sub.routes or []) + (entry.get("routes") or []) + web.detected_routes)) or ["BGP"]
        clients = list(dict.fromkeys((entry.get("clients") or []) + web.detected_clients)) or ["Clash Verge", "v2rayN"]
        payments = list(dict.fromkeys((entry.get("payments") or []) + web.detected_payments)) or ["公开研究"]
        nodes_count = sub.node_count if sub.node_count > 0 else int(entry.get("nodes") or 0)
        probe_mode = sub.mode if sub.probed else "web_health"

        if status == "risk":
            summary = risk_reason or f"自动化探测连续 {consecutive_failures} 次异常（可用率 {uptime_pct:.1f}%），已触发风险观察。"
        elif status == "watch":
            summary = f"近期连通性存在波动（探测可用率 {uptime_pct:.1f}%、中位延迟 {latency_ms:.0f}ms），持续观测中。"
        else:
            summary = str(
                entry.get("summary")
                or f"自动化探测正常：解析 {nodes_count} 个节点，抽样握手可用率 {uptime_pct:.1f}%，中位延迟 {latency_ms:.0f}ms。"
            )

    cst = now.astimezone(timezone(timedelta(hours=8)))
    slot_name = "peak" if cst.hour >= 18 else "normal"
    slot_key = f"{cst.strftime('%Y-%m-%d')}#{slot_name}"

    if is_risk_entry:
        data_tier = "risk_listed"
        health_status = "down"
    elif sub.probed:
        data_tier = "sub_probed"
        health_status = "ok" if (sub.uptime_pct or 0) >= 50 else "down"
    elif is_directory_only:
        data_tier = "directory_only"
        health_status = "skipped"
    else:
        data_tier = "web_monitored"
        if web.ok:
            health_status = "ok"
        elif web.dns_ok and web.waf_protected:
            health_status = "waf_protected"
        else:
            health_status = "down"

    daily_map: dict[str, dict[str, float]] = dict(prev_state.get("daily") or {})
    daily_map[today] = {
        "score": total_score,
        "uptime": round(uptime_pct, 2),
        "speed": round(speed_mbps, 2),
        "latency": round(latency_ms, 2),
        "loss": round(loss_pct, 2),
    }
    sorted_days = sorted(daily_map.keys())[-30:]
    trimmed_daily = {d: daily_map[d] for d in sorted_days}

    slots_map: dict[str, dict[str, Any]] = dict(prev_state.get("slots") or {})
    slots_map[slot_key] = {
        "key": slot_key,
        "slot": slot_name,
        "uptime": round(uptime_pct, 2),
        "ttfbMs": round(web.ttfb_ms, 2) if web.ttfb_ms is not None else None,
        "latency": round(latency_ms, 2),
        "score": total_score,
        "health": health_status,
    }
    sorted_slots = sorted(slots_map.keys())[-60:]
    trimmed_slots = {k: slots_map[k] for k in sorted_slots}
    slot_history = [trimmed_slots[k] for k in sorted_slots]

    history = {
        "score": _pad_series([trimmed_daily[d]["score"] for d in sorted_days]),
        "uptime": _pad_series([trimmed_daily[d]["uptime"] for d in sorted_days]),
        "speed": _pad_series([trimmed_daily[d]["speed"] for d in sorted_days]),
        "latency": _pad_series([trimmed_daily[d]["latency"] for d in sorted_days]),
        "loss": _pad_series([trimmed_daily[d]["loss"] for d in sorted_days]),
    }

    clean_streaming = [s for s in (entry.get("streaming") or []) if s and "未测" not in str(s)]
    official_url = str(entry.get("officialUrl") or "").strip()
    if not official_url:
        w = str(entry.get("website") or "#").strip()
        if w.startswith(("http://", "https://")) and "github.com" not in w.lower():
            official_url = w

    airport_record: dict[str, Any] = {
        "slug": entry["slug"],
        "name": entry["name"],
        "color": entry.get("color") or "#0d9488",
        "status": status,
        "dataTier": data_tier,
        "officialUrl": official_url,
        "nodes": nodes_count,
        "priceMonthly": float(entry.get("priceMonthly") if entry.get("priceMonthly") is not None else 15.0),
        "observedDays": observed_days,
        "historyPoints": len(slot_history),
        "score": total_score,
        "scores": scores,
        "trial": bool(entry.get("trial") or web.detected_trial),
        "refund": bool(entry.get("refund") or web.detected_refund),
        "founded": str(entry.get("founded") or web.founded_rdap or ""),
        "tags": list(entry.get("tags") or []),
        "regions": regions,
        "routes": routes,
        "clients": clients,
        "streaming": clean_streaming,
        "payments": payments,
        "importMethods": list(entry.get("importMethods") or ["一键订阅"]),
        "plans": list(entry.get("plans") or []),
        "telegram": entry.get("telegram") or {},
        "history": history,
        "slotHistory": slot_history,
        "summary": summary,
        "website": entry.get("website") or "#",
        "probeMeta": {
            "mode": probe_mode,
            "dataTier": data_tier,
            "checkedAt": now.isoformat(),
            "slot": slot_name,
            "healthStatus": health_status,
            "httpStatus": web.http_status,
            "ttfbMs": web.ttfb_ms,
            "dnsOk": web.dns_ok,
            "tlsOk": web.tls_ok,
            "tlsDaysLeft": web.tls_days_left,
            "panelType": web.panel_type,
            "consecutiveFailures": consecutive_failures,
            "externalRisk": risk_reason if is_risk_entry else "",
            "probeRisk": f"连续 {consecutive_failures} 次探测异常" if consecutive_failures >= 2 else "",
            "protocols": sub.protocols,
        },
    }
    if isinstance(entry.get("ratingMeta"), dict):
        airport_record["ratingMeta"] = entry["ratingMeta"]
    if isinstance(entry.get("publicBench"), dict):
        airport_record["publicBench"] = entry["publicBench"]

    next_state = {
        "first_seen": first_seen,
        "observed_days": observed_days,
        "consecutive_failures": consecutive_failures,
        "total_probes": int(prev_state.get("total_probes") or 0) + max(1, sub.sample_count),
        "daily": trimmed_daily,
        "slots": trimmed_slots,
    }
    return airport_record, next_state


def build_monthly_report(airports: list[dict[str, Any]], now: datetime | None = None) -> ReportRecord:
    now = now or datetime.now(timezone.utc)
    month_key = now.strftime("%Y.%m")
    year_str = now.strftime("%Y")
    ranked = sorted(airports, key=lambda x: x.get("score", 0), reverse=True)
    top_names = "、".join(a["name"] for a in ranked[:3]) if ranked else "暂无"
    return ReportRecord(
        month=month_key,
        year=year_str,
        title=f"{now.year} 年 {now.month} 月自动化探测与稳定性月报",
        sample=len(airports),
        top=top_names,
        tags=["自动化探测", "S-P-N-C-R", "纯技术学习"],
    )
