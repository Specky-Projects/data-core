from __future__ import annotations

import json
import time

from app.runtime.scheduler_watchdog import (
    DataCoreSchedulerWatchdog,
    SchedulerDiagnosis,
    TREND_MEMORY_GROWING,
    TREND_MEMORY_STABLE,
    format_scheduler_alert_payload,
    format_scheduler_telegram_message,
)


def _write_snapshot(path, **overrides):
    payload = {
        "timestamp_epoch": time.time(),
        "container_name": "scheduler-test",
        "memory_usage_bytes": 160 * 1024 * 1024,
        "memory_limit_bytes": 768 * 1024 * 1024,
        "swap_usage_ratio": 0.10,
        "observed_restart_count": 0,
        "oom_kill_count": 0,
        "oom_recent": False,
        "growth_rate_bytes_per_second": 0.0,
        "trend_state": TREND_MEMORY_STABLE,
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_scheduler_watchdog_healthy_after_mitigation(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _write_snapshot(snapshot)

    diagnosis = DataCoreSchedulerWatchdog(snapshot).diagnose()

    assert diagnosis.operational_state == "SCHEDULER_HEALTHY"
    assert diagnosis.alert_severity == "info"
    assert diagnosis.memory_usage_ratio < 0.25


def test_scheduler_watchdog_memory_elevated_is_preventive_info(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _write_snapshot(snapshot, memory_usage_bytes=int(0.65 * 768 * 1024 * 1024))

    diagnosis = DataCoreSchedulerWatchdog(snapshot).diagnose()

    assert diagnosis.operational_state == "SCHEDULER_MEMORY_ELEVATED"
    assert diagnosis.alert_severity == "info"


def test_scheduler_watchdog_memory_high_is_warning(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _write_snapshot(snapshot, memory_usage_bytes=int(0.78 * 768 * 1024 * 1024))

    diagnosis = DataCoreSchedulerWatchdog(snapshot).diagnose()

    assert diagnosis.operational_state == "SCHEDULER_MEMORY_HIGH"
    assert diagnosis.alert_severity == "warning"


def test_scheduler_watchdog_memory_critical_precedes_oom(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _write_snapshot(snapshot, memory_usage_bytes=int(0.93 * 768 * 1024 * 1024))

    diagnosis = DataCoreSchedulerWatchdog(snapshot).diagnose()

    assert diagnosis.operational_state == "SCHEDULER_MEMORY_CRITICAL"
    assert diagnosis.alert_severity == "critical"


def test_scheduler_watchdog_oom_recent_is_critical(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _write_snapshot(snapshot, oom_recent=True, oom_kill_count=1)

    diagnosis = DataCoreSchedulerWatchdog(snapshot).diagnose()

    assert diagnosis.operational_state == "SCHEDULER_OOM_RECENT"
    assert diagnosis.alert_severity == "critical"


def test_scheduler_watchdog_restart_loop_is_critical(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _write_snapshot(snapshot, observed_restart_count=3, restart_count_source="docker")

    diagnosis = DataCoreSchedulerWatchdog(snapshot).diagnose()

    assert diagnosis.operational_state == "SCHEDULER_RESTART_LOOP"
    assert diagnosis.alert_severity == "critical"
    assert diagnosis.real_restart_count == 3
    assert diagnosis.false_restart_count == 0


def test_scheduler_watchdog_legacy_restart_count_is_not_real_loop(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _write_snapshot(snapshot, observed_restart_count=3)

    diagnosis = DataCoreSchedulerWatchdog(snapshot).diagnose()

    assert diagnosis.operational_state == "OBSERVE_MORE"
    assert diagnosis.alert_severity == "warning"
    assert diagnosis.real_restart_count == 0
    assert diagnosis.false_restart_count == 3
    assert diagnosis.restart_provenance == "legacy_or_probe_local"
    assert diagnosis.watchdog_confidence_score < 0.5


def test_scheduler_watchdog_growth_without_pressure_observes_more(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _write_snapshot(snapshot, trend_state="POSSIBLE_MEMORY_LEAK", growth_rate_bytes_per_second=1024)

    diagnosis = DataCoreSchedulerWatchdog(snapshot).diagnose()

    assert diagnosis.operational_state == "OBSERVE_MORE"
    assert diagnosis.alert_severity == "warning"


def test_scheduler_watchdog_stale_snapshot_is_degraded(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _write_snapshot(snapshot, timestamp_epoch=time.time() - 1000)

    diagnosis = DataCoreSchedulerWatchdog(snapshot, stale_after_seconds=60).diagnose()

    assert diagnosis.operational_state == "SCHEDULER_DEGRADED"
    assert diagnosis.alert_severity == "warning"


def test_scheduler_telegram_payload_distinguishes_healthy_from_oom(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _write_snapshot(snapshot, trend_state=TREND_MEMORY_GROWING)
    healthy = DataCoreSchedulerWatchdog(snapshot).diagnose()
    message = format_scheduler_telegram_message(healthy)

    assert "Scheduler saudavel" in message
    assert "OOM recente: nao" in message
    assert "SCHEDULER_HEALTHY" in message

    _write_snapshot(snapshot, oom_recent=True, oom_kill_count=2)
    critical = DataCoreSchedulerWatchdog(snapshot).diagnose()
    message = format_scheduler_telegram_message(critical)

    assert "Scheduler proximo de OOM" in message
    assert "OOM recente: sim" in message
    assert "SCHEDULER_OOM_RECENT" in message


def test_scheduler_summary_contains_ops_fields(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _write_snapshot(snapshot, memory_usage_bytes=int(0.21 * 768 * 1024 * 1024))

    summary = DataCoreSchedulerWatchdog(snapshot).diagnose().to_summary()

    assert set(summary) == {
        "state",
        "severity",
        "memory_usage_ratio",
        "memory_usage_percent",
        "swap_usage_ratio",
        "swap_usage_percent",
        "restart_count",
        "oom_recent",
        "trend",
        "recommendation",
        "restart_provenance",
        "real_restart_count",
        "false_restart_count",
        "heartbeat_age_seconds",
        "watchdog_confidence_score",
        "execution_drift_seconds",
        "runtime_memory_pressure_score",
    }
    assert summary["state"] == "SCHEDULER_HEALTHY"
    assert summary["severity"] == "info"
    assert summary["oom_recent"] is False


def test_scheduler_alert_payload_events(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _write_snapshot(snapshot, memory_usage_bytes=int(0.78 * 768 * 1024 * 1024))

    warning = DataCoreSchedulerWatchdog(snapshot).diagnose()
    payload = format_scheduler_alert_payload(warning)

    assert payload["event"] == "warning"
    assert payload["severity"] == "warning"
    assert "Scheduler com pressao preventiva" in payload["text"]

    recovered = format_scheduler_alert_payload(warning, event="recovered")
    assert recovered["event"] == "recovered"
    assert "Scheduler recuperado" in recovered["text"]


def test_scheduler_degraded_payload(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _write_snapshot(snapshot, timestamp_epoch=time.time() - 1000)

    degraded = DataCoreSchedulerWatchdog(snapshot, stale_after_seconds=60).diagnose()
    payload = format_scheduler_alert_payload(degraded)

    assert payload["event"] == "degraded"
    assert payload["summary"]["state"] == "SCHEDULER_DEGRADED"


def test_scheduler_metrics_exposition(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _write_snapshot(snapshot, memory_usage_bytes=int(0.65 * 768 * 1024 * 1024))

    diagnosis = DataCoreSchedulerWatchdog(snapshot).diagnose()

    from api import metrics

    assert metrics.data_core_scheduler_memory_usage_ratio._value.get() == diagnosis.memory_usage_ratio
    assert metrics.data_core_scheduler_state._value.get() == 1
    assert metrics.data_core_scheduler_alert_severity._value.get() == 0
    assert metrics.scheduler_false_restart_total._value.get() == 0
    assert metrics.scheduler_execution_drift_seconds._value.get() == diagnosis.execution_drift_seconds
    assert metrics.watchdog_confidence_score._value.get() == diagnosis.watchdog_confidence_score


def test_scheduler_trend_detection_possible_leak():
    from app.runtime.scheduler_watchdog import _trend_state

    samples = [
        {"timestamp_epoch": 1, "memory_usage_bytes": 100},
        {"timestamp_epoch": 2, "memory_usage_bytes": 140},
        {"timestamp_epoch": 3, "memory_usage_bytes": 180},
        {"timestamp_epoch": 4, "memory_usage_bytes": 230},
    ]

    assert _trend_state(samples, memory_limit=1000) == "POSSIBLE_MEMORY_LEAK"


def test_summary_endpoint_uses_diagnosis(monkeypatch):
    from app.runtime import api

    diagnosis = SchedulerDiagnosis(
        container_name="scheduler",
        memory_usage_bytes=10,
        memory_limit_bytes=100,
        memory_usage_ratio=0.1,
        swap_usage_ratio=0.0,
        restart_count=0,
        oom_recent=False,
        oom_total=0,
        growth_rate=0.0,
        trend_state="MEMORY_STABLE",
        operational_state="SCHEDULER_HEALTHY",
        alert_severity="info",
        cycle_duration=1.0,
        backlog_score=0.0,
        explanation="ok",
        recommended_action="No action required.",
    )

    class FakeWatchdog:
        def diagnose(self, db=None):
            return diagnosis

    monkeypatch.setattr(api, "DataCoreSchedulerWatchdog", lambda: FakeWatchdog())

    summary = api.scheduler_summary(db=None)
    payload = api.scheduler_alert_payload(db=None)

    assert summary["state"] == "SCHEDULER_HEALTHY"
    assert payload["event"] == "healthy"


def test_no_false_positive_when_healthy(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    _write_snapshot(snapshot, memory_usage_bytes=int(0.20 * 768 * 1024 * 1024), swap_usage_ratio=0)

    diagnosis = DataCoreSchedulerWatchdog(snapshot).diagnose()
    payload = format_scheduler_alert_payload(diagnosis)

    assert diagnosis.operational_state == "SCHEDULER_HEALTHY"
    assert diagnosis.alert_severity == "info"
    assert payload["event"] == "healthy"


def test_scheduler_execution_drift_is_recorded(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from app.runtime import scheduler_watchdog

    drift_path = tmp_path / "drift.jsonl"
    monkeypatch.setattr(scheduler_watchdog, "DRIFT_PATH", drift_path)
    scheduled = datetime.now(tz=timezone.utc) - timedelta(seconds=42)

    drift = scheduler_watchdog.record_scheduler_execution_event(
        event="job_executed",
        job_id="pipeline:normalize",
        scheduled_run_time=scheduled,
    )

    assert drift >= 40
    payload = json.loads(drift_path.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["job_id"] == "pipeline:normalize"
    assert payload["execution_drift_seconds"] >= 40
