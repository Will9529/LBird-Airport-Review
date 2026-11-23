from datetime import datetime, timedelta, timezone
from pathlib import Path

from lbird.exporter import export_all, validate_data_dir
from lbird.models import SubProbeResult, TelegramResult, WebHealthResult
from lbird.scoring import build_monthly_report, compute_weighted_score, evaluate_target


def test_weighted_score_and_status_transitions():
    assert compute_weighted_score({"S": 90, "P": 80, "N": 85, "C": 95, "R": 90}) == 87.25

    entry = {"slug": "sample-a", "name": "Sample A", "website": "https://example.org", "priceMonthly": 0}
    now = datetime(2026, 11, 24, 0, 0, tzinfo=timezone.utc)

    # Normal run
    rec1, st1 = evaluate_target(
        entry,
        WebHealthResult(url="https://example.org", ok=True, dns_ok=True, tls_ok=True, http_status=200, ttfb_ms=60.0),
        TelegramResult(),
        SubProbeResult(probed=True, mode="tcp_passive", node_count=20, sample_count=10, reachable_count=10, uptime_pct=100.0, latency_ms=55.0, loss_pct=0.0),
        "",
        {},
        now=now,
    )
    assert rec1["status"] == "normal"
    assert len(rec1["history"]["score"]) >= 2

    # 3 consecutive failures -> risk
    st = st1
    for day in range(1, 4):
        rec_f, st = evaluate_target(
            entry,
            WebHealthResult(url="https://example.org", ok=False, dns_ok=False, tls_ok=False, error="dns_failed"),
            TelegramResult(),
            SubProbeResult(probed=True, mode="tcp_passive", node_count=0, sample_count=10, reachable_count=0, uptime_pct=0.0, latency_ms=400.0, loss_pct=100.0),
            "",
            st,
            now=now + timedelta(days=day),
        )
    assert rec_f["status"] == "risk"
    assert st["consecutive_failures"] == 3


def test_export_and_secret_leak_validator(tmp_path: Path):
    now = datetime(2026, 11, 24, 0, 0, tzinfo=timezone.utc)
    airports = [
        {
            "slug": "safe-oss",
            "name": "Safe OSS",
            "status": "normal",
            "score": 88.5,
            "nodes": 12,
            "history": {"score": [88.5, 88.5], "uptime": [99, 99], "speed": [120, 120], "latency": [45, 45], "loss": [0, 0]},
        }
    ]
    report = build_monthly_report(airports, now)
    export_all(tmp_path, airports, [], [], report, {"targets": {"safe-oss": {"total_probes": 10}}}, now)
    assert validate_data_dir(tmp_path) == []

    # Inject a forbidden URI leak and confirm validator catches it
    (tmp_path / "airports.json").write_text('[{"summary": "trojan://secret@1.2.3.4:443"}]', encoding="utf-8")
    errs = validate_data_dir(tmp_path)
    assert any("secret_leak_detected" in e for e in errs)
