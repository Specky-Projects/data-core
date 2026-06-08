"""Phase 3 tests: analytics counters, MTTR, incidents, daily report, healers."""
from __future__ import annotations

import json
import math
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.auto_healing.analytics import (
    DailyReport,
    DailyReporter,
    GlobalMetrics,
    HistoryReader,
    IncidentRecord,
    MetricsCollector,
    ServiceMetrics,
    _parse_ts,
    _status_ok,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _entry(ts: datetime, health: dict[str, str], heals: list[dict] | None = None) -> dict:
    """Build a minimal watchdog history entry."""
    return {
        "timestamp": ts.isoformat(),
        "status": "DEGRADED",
        "dry_run": False,
        "service_health": [{"name": k, "status": v} for k, v in health.items()],
        "heal_results": heals or [],
        "errors": [],
    }


def _write_history(entries: list[dict], path: Path) -> None:
    with path.open("w") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")


BASE = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)


# ── _status_ok ────────────────────────────────────────────────────────────────

def test_status_ok_truthy():
    for s in ("OK", "ok", "READY", "HEALTHY", "ALIVE"):
        assert _status_ok(s), f"Expected {s!r} to be ok"


def test_status_ok_falsy():
    for s in ("DEGRADED", "DOWN", "CRITICAL", "ERROR", ""):
        assert not _status_ok(s), f"Expected {s!r} to not be ok"


# ── _parse_ts ─────────────────────────────────────────────────────────────────

def test_parse_ts_iso():
    ts = _parse_ts("2026-06-08T12:00:00+00:00")
    assert ts is not None
    assert ts.year == 2026


def test_parse_ts_z_suffix():
    ts = _parse_ts("2026-06-08T12:00:00Z")
    assert ts is not None


def test_parse_ts_empty():
    assert _parse_ts("") is None
    assert _parse_ts(None) is None  # type: ignore[arg-type]


# ── HistoryReader — read_entries ──────────────────────────────────────────────

def test_history_reader_empty_file():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
        path = Path(f.name)
    reader = HistoryReader(history_path=str(path))
    assert reader.read_entries() == []


def test_history_reader_filters_by_window():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False, encoding="utf-8") as f:
        path = Path(f.name)

    now = datetime.now(timezone.utc)
    old = now - timedelta(hours=200)
    recent = now - timedelta(hours=2)
    entries = [
        _entry(old, {"redis": "OK"}),
        _entry(recent, {"redis": "DEGRADED"}),
    ]
    _write_history(entries, path)

    reader = HistoryReader(history_path=str(path))
    result = reader.read_entries(window_hours=24)
    assert len(result) == 1
    assert "DEGRADED" in result[0]["service_health"][0]["status"]


# ── HistoryReader — extract_incidents ─────────────────────────────────────────

def test_extract_incidents_single_recovery():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False, encoding="utf-8") as f:
        path = Path(f.name)

    entries = [
        _entry(BASE, {"redis": "DEGRADED"}),
        _entry(BASE + timedelta(seconds=30), {"redis": "OK"},
               heals=[{"service": "redis", "outcome": "RECOVERED"}]),
    ]
    _write_history(entries, path)

    reader = HistoryReader(history_path=str(path))
    incidents = reader.extract_incidents(window_hours=168)
    recovered = [i for i in incidents if i.outcome == "recovered" and i.service == "redis"]
    assert len(recovered) == 1
    inc = recovered[0]
    assert inc.duration_seconds is not None
    assert inc.duration_seconds == pytest.approx(30.0, abs=1)
    assert inc.heal_attempts == 1


def test_extract_incidents_open_incident():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False, encoding="utf-8") as f:
        path = Path(f.name)

    # Redis degraded but never recovered within window
    entries = [
        _entry(BASE, {"redis": "DEGRADED"}),
        _entry(BASE + timedelta(minutes=5), {"redis": "DEGRADED"}),
    ]
    _write_history(entries, path)

    reader = HistoryReader(history_path=str(path))
    incidents = reader.extract_incidents(window_hours=168)
    open_inc = [i for i in incidents if i.outcome == "open" and i.service == "redis"]
    assert len(open_inc) == 1


def test_extract_incidents_multiple_services():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False, encoding="utf-8") as f:
        path = Path(f.name)

    entries = [
        _entry(BASE, {"redis": "DEGRADED", "workers": "DEGRADED"}),
        _entry(BASE + timedelta(seconds=35), {"redis": "OK", "workers": "OK"},
               heals=[
                   {"service": "redis", "outcome": "RECOVERED"},
                   {"service": "workers", "outcome": "RECOVERED"},
               ]),
    ]
    _write_history(entries, path)

    reader = HistoryReader(history_path=str(path))
    incidents = reader.extract_incidents(window_hours=168)
    recovered = [i for i in incidents if i.outcome == "recovered"]
    assert len(recovered) == 2
    services = {i.service for i in recovered}
    assert "redis" in services
    assert "workers" in services


# ── HistoryReader — compute_mttr ──────────────────────────────────────────────

def test_compute_mttr_basic():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False, encoding="utf-8") as f:
        path = Path(f.name)

    # Two recovered incidents: 30s and 60s → avg=45, p95=60
    entries = [
        _entry(BASE, {"redis": "DEGRADED"}),
        _entry(BASE + timedelta(seconds=30), {"redis": "OK"}),
        _entry(BASE + timedelta(seconds=60), {"redis": "DEGRADED"}),
        _entry(BASE + timedelta(seconds=120), {"redis": "OK"}),
    ]
    _write_history(entries, path)

    reader = HistoryReader(history_path=str(path))
    mttr = reader.compute_mttr(window_hours=168)
    assert "redis" in mttr
    assert mttr["redis"]["count"] == 2
    assert mttr["redis"]["avg_seconds"] == pytest.approx(45.0, abs=2)


def test_compute_mttr_no_recovery():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False, encoding="utf-8") as f:
        path = Path(f.name)

    entries = [_entry(BASE, {"redis": "DEGRADED"})]
    _write_history(entries, path)

    reader = HistoryReader(history_path=str(path))
    mttr = reader.compute_mttr(window_hours=168)
    assert "redis" not in mttr


# ── HistoryReader — healer_stats ──────────────────────────────────────────────

def test_healer_stats():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False, encoding="utf-8") as f:
        path = Path(f.name)

    entries = [
        _entry(BASE, {"redis": "DEGRADED"},
               heals=[{"service": "redis", "outcome": "RECOVERED"}]),
        _entry(BASE + timedelta(hours=1), {"workers": "DEGRADED"},
               heals=[{"service": "workers", "outcome": "FAILED"}]),
        _entry(BASE + timedelta(hours=2), {"workers": "DEGRADED"},
               heals=[{"service": "workers", "outcome": "SKIPPED"}]),
    ]
    _write_history(entries, path)

    reader = HistoryReader(history_path=str(path))
    stats = reader.healer_stats(window_hours=168)

    redis_stats = next(s for s in stats if s["target_service"] == "redis")
    workers_stats = next(s for s in stats if s["target_service"] == "workers")

    assert redis_stats["recovered"] == 1
    assert redis_stats["success_rate"] == pytest.approx(1.0)
    assert workers_stats["failed"] == 1
    assert workers_stats["skipped"] == 1
    assert workers_stats["success_rate"] == pytest.approx(0.0)


# ── MetricsCollector — record_run ────────────────────────────────────────────

def test_metrics_collector_record_run_no_crash():
    """record_run must never raise, even with a fake execution dict."""
    collector = MetricsCollector()
    fake_redis = MagicMock()
    with patch("app.auto_healing.analytics._redis", return_value=fake_redis):
        collector.record_run({
            "heal_results": [{"service": "redis", "outcome": "RECOVERED"}],
            "service_health": [{"name": "redis", "status": "OK"}],
        })
    fake_redis.incr.assert_called()


def test_metrics_collector_counts_all_outcomes():
    from app.auto_healing.models import HealOutcome
    collector = MetricsCollector()
    incr_calls: list[str] = []
    fake_redis = MagicMock()
    fake_redis.incr.side_effect = lambda k: incr_calls.append(k)
    fake_redis.mget.return_value = [0] * 9

    with patch("app.auto_healing.analytics._redis", return_value=fake_redis):
        collector.record_run({
            "heal_results": [
                {"service": "redis", "outcome": "RECOVERED"},
                {"service": "workers", "outcome": "FAILED"},
                {"service": "scheduler", "outcome": "SKIPPED"},
                {"service": "api", "outcome": "BLOCKED_CIRCUIT"},
            ],
            "service_health": [],
        })

    attempted_keys = [k for k in incr_calls if "heals_attempted" in k]
    successful_keys = [k for k in incr_calls if "heals_successful" in k]
    failed_keys = [k for k in incr_calls if "heals_failed" in k]
    cooldown_keys = [k for k in incr_calls if "cooldown_blocks" in k]
    circuit_keys = [k for k in incr_calls if "circuit_opens" in k]

    assert len(attempted_keys) == 4
    assert len(successful_keys) == 1
    assert len(failed_keys) == 1
    assert len(cooldown_keys) == 1
    assert len(circuit_keys) == 1


# ── ServiceMetrics — to_dict ──────────────────────────────────────────────────

def test_service_metrics_to_dict_rounds():
    m = ServiceMetrics(
        service="redis",
        incidents_total=3,
        heals_attempted=5,
        heals_successful=4,
        heal_success_rate=0.8,
        mttr_avg_seconds=33.333333,
        mttr_p95_seconds=42.1234567,
    )
    d = m.to_dict()
    assert d["mttr_avg_seconds"] == pytest.approx(33.333, abs=0.001)
    assert d["mttr_p95_seconds"] == pytest.approx(42.123, abs=0.001)
    assert d["heal_success_rate"] == pytest.approx(0.8, abs=0.001)


# ── DailyReport — to_text ────────────────────────────────────────────────────

def test_daily_report_to_text_contains_key_fields():
    report = DailyReport(
        report_date="2026-06-08",
        incidents=2,
        heals_attempted=3,
        heals_successful=2,
        heals_failed=1,
        cooldown_blocks=0,
        circuit_opens=0,
        recoveries=2,
        heal_success_rate=0.667,
        mttr_avg_seconds=35.0,
    )
    text = report.to_text()
    assert "2026-06-08" in text
    assert "2" in text    # incidents
    assert "35" in text   # mttr
    assert "66.7%" in text  # success rate


# ── GlobalMetrics — to_dict ───────────────────────────────────────────────────

def test_global_metrics_to_dict_structure():
    gm = GlobalMetrics(
        window_hours=168,
        generated_at="2026-06-08T20:00:00+00:00",
        incidents_total=5,
        heals_attempted=8,
        heals_successful=6,
        heal_success_rate=0.75,
    )
    d = gm.to_dict()
    assert "global" in d
    assert "by_service" in d
    assert d["global"]["heal_success_rate"] == pytest.approx(0.75)
