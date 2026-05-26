from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.runtime.scheduler_reliability import (
    BacklogSignals,
    MIN_CALIBRATION_DECISIONS,
    MIN_CALIBRATION_HOURS,
    SchedulerReliabilityEngine,
    classify_protection_mode,
    recommend_actions,
    read_reliability_audit_events,
    readiness_recommendation,
    scheduler_reliability_audit_report,
    summarize_reliability_audit,
)
from app.runtime.scheduler_watchdog import SchedulerDiagnosis


def _diagnosis(**overrides):
    payload = {
        "container_name": "scheduler",
        "memory_usage_bytes": 150,
        "memory_limit_bytes": 768,
        "memory_usage_ratio": 0.20,
        "swap_usage_ratio": 0.0,
        "restart_count": 0,
        "oom_recent": False,
        "oom_total": 0,
        "growth_rate": 0.0,
        "trend_state": "MEMORY_STABLE",
        "operational_state": "SCHEDULER_HEALTHY",
        "alert_severity": "info",
        "cycle_duration": 10.0,
        "backlog_score": 0.0,
        "explanation": "ok",
        "recommended_action": "No action required.",
    }
    payload.update(overrides)
    return SchedulerDiagnosis(**payload)


def _backlog(**overrides):
    payload = {
        "pending_total": 0,
        "growth_rate": 0.0,
        "pressure_score": 0.0,
        "throughput_estimate": 10.0,
        "starvation_detected": False,
        "explosive_growth": False,
        "stuck_jobs": 0,
    }
    payload.update(overrides)
    return BacklogSignals(**payload)


def _audit_event(timestamp: datetime, **overrides):
    payload = {
        "timestamp": timestamp.isoformat(),
        "job_name": "normalize_job",
        "priority": "HIGH",
        "mode": "NORMAL",
        "enabled": False,
        "dry_run": True,
        "concurrency": 2,
        "batch_size": 100,
        "cooldown_seconds": 0.0,
        "low_priority_delay_seconds": 0.0,
        "throttled": False,
        "throttle_reason": None,
        "backlog": {
            "pending_total": 0,
            "growth_rate": 0.0,
            "pressure_score": 0.0,
            "throughput_estimate": 10.0,
            "starvation_detected": False,
            "explosive_growth": False,
            "stuck_jobs": 0,
        },
        "recommendations": ["Manter execucao normal; nenhuma acao requerida."],
        "diagnosis_state": "SCHEDULER_HEALTHY",
        "severity": "info",
        "memory_usage_ratio": 0.2,
        "swap_usage_ratio": 0.0,
        "memory_growth_rate": 0.0,
        "cycle_duration_seconds": 10.0,
    }
    payload.update(overrides)
    return payload


def _write_events(path, events):
    path.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")


def test_protection_mode_normal_when_healthy():
    assert classify_protection_mode(_diagnosis(), _backlog()) == "NORMAL"


def test_protection_mode_conservative_for_memory_elevated():
    d = _diagnosis(memory_usage_ratio=0.61, operational_state="SCHEDULER_MEMORY_ELEVATED")
    assert classify_protection_mode(d, _backlog()) == "CONSERVATIVE"


def test_protection_mode_protective_for_memory_pressure():
    d = _diagnosis(
        memory_usage_ratio=0.78,
        operational_state="SCHEDULER_MEMORY_HIGH",
        alert_severity="warning",
    )
    assert classify_protection_mode(d, _backlog()) == "PROTECTIVE"


def test_protection_mode_critical_for_oom_recent():
    d = _diagnosis(
        oom_recent=True,
        operational_state="SCHEDULER_OOM_RECENT",
        alert_severity="critical",
    )
    assert classify_protection_mode(d, _backlog()) == "CRITICAL_PROTECTION"


def test_backlog_explosive_growth_forces_protective():
    b = _backlog(pending_total=300, growth_rate=2.0, pressure_score=0.3, explosive_growth=True)
    assert classify_protection_mode(_diagnosis(), b) == "PROTECTIVE"


def test_recommendations_include_low_priority_throttle():
    recs = recommend_actions(_diagnosis(memory_usage_ratio=0.80), _backlog(), "PROTECTIVE", "LOW")
    assert any("jobs LOW" in item for item in recs)


def test_decision_dry_run_does_not_change_callable(monkeypatch, tmp_path):
    from app.runtime import scheduler_reliability as sr

    monkeypatch.setattr(sr.settings, "scheduler_reliability_enabled", True)
    monkeypatch.setattr(sr.settings, "scheduler_reliability_dry_run", True)

    engine = SchedulerReliabilityEngine(audit_path=tmp_path / "audit.jsonl")
    calls = []

    def job(limit=100):
        calls.append(limit)
        return "ok"

    result = engine.run("analytics_job", job, supports_limit=True, default_limit=100)

    assert result == "ok"
    assert calls == [100]
    assert (tmp_path / "audit.jsonl").exists()


def test_decision_applies_batch_only_when_enabled_not_dry_run(monkeypatch, tmp_path):
    from app.runtime import scheduler_reliability as sr

    monkeypatch.setattr(sr.settings, "scheduler_reliability_enabled", True)
    monkeypatch.setattr(sr.settings, "scheduler_reliability_dry_run", False)
    monkeypatch.setattr(sr.settings, "scheduler_reliability_protective_cooldown_seconds", 0.0)
    monkeypatch.setattr(
        sr.DataCoreSchedulerWatchdog,
        "diagnose",
        lambda self, db=None: _diagnosis(
            memory_usage_ratio=0.80,
            operational_state="SCHEDULER_MEMORY_HIGH",
            alert_severity="warning",
        ),
    )

    engine = SchedulerReliabilityEngine(audit_path=tmp_path / "audit.jsonl")
    calls = []

    def job(limit=100):
        calls.append(limit)
        return "ok"

    result = engine.run("analytics_job", job, supports_limit=True, default_limit=100)

    assert result == "ok"
    assert calls == [50]


def test_read_reliability_audit_jsonl_tolerates_corrupt_lines(tmp_path):
    audit = tmp_path / "audit.jsonl"
    audit.write_text(
        "\n".join(
            item if isinstance(item, str) else json.dumps(item)
            for item in [
                {
                    "timestamp": "2026-05-23T10:00:00+00:00",
                    "mode": "NORMAL",
                    "priority": "HIGH",
                    "dry_run": True,
                    "backlog": {"growth_rate": 0, "pressure_score": 0.1, "pending_total": 5},
                },
                "not-json",
                {
                    "timestamp": "2026-05-23T10:01:00+00:00",
                    "mode": "CONSERVATIVE",
                    "priority": "LOW",
                    "dry_run": True,
                    "severity": "info",
                    "diagnosis_state": "SCHEDULER_HEALTHY",
                    "memory_usage_ratio": 0.2,
                    "backlog": {"growth_rate": 0, "pressure_score": 0.1, "pending_total": 5},
                },
            ]
        ),
        encoding="utf-8",
    )

    events, health = read_reliability_audit_events(audit)

    assert len(events) == 2
    assert health["corrupt_lines"] == 1


def test_audit_report_filters_and_aggregates_decisions(tmp_path):
    audit = tmp_path / "audit.jsonl"
    audit.write_text(
        "\n".join(
            json.dumps(item)
            for item in [
                {
                    "timestamp": "2026-05-23T10:00:00+00:00",
                    "mode": "NORMAL",
                    "priority": "HIGH",
                    "dry_run": True,
                    "memory_usage_ratio": 0.2,
                    "backlog": {"growth_rate": 0, "pressure_score": 0.1, "pending_total": 5},
                },
                {
                    "timestamp": "2026-05-23T10:01:00+00:00",
                    "mode": "PROTECTIVE",
                    "priority": "LOW",
                    "dry_run": True,
                    "severity": "warning",
                    "diagnosis_state": "SCHEDULER_MEMORY_HIGH",
                    "memory_usage_ratio": 0.8,
                    "memory_growth_rate": 10,
                    "backlog": {"growth_rate": 2, "pressure_score": 0.8, "pending_total": 900},
                },
            ]
        ),
        encoding="utf-8",
    )

    report = scheduler_reliability_audit_report(audit, mode="PROTECTIVE", job_priority="LOW")
    summary = report["summary"]

    assert summary["total_events"] == 1
    assert summary["mode_counts"] == {"PROTECTIVE": 1}
    assert summary["dry_run_decisions_total"] == 1
    assert summary["max_observed"]["memory_usage_ratio"] == 0.8
    assert summary["growth_rate"]["max_backlog_growth_rate"] == 2.0


def test_audit_summary_detects_mode_changes_and_false_positive_candidates():
    events = [
        {"mode": "NORMAL", "priority": "HIGH", "dry_run": True, "backlog": {"pressure_score": 0}},
        {
            "mode": "CONSERVATIVE",
            "priority": "NORMAL",
            "dry_run": True,
            "severity": "info",
            "diagnosis_state": "SCHEDULER_HEALTHY",
            "memory_usage_ratio": 0.2,
            "backlog": {"growth_rate": 0, "pressure_score": 0.1},
        },
    ]

    summary = summarize_reliability_audit(events)

    assert summary["mode_changes_total"] == 1
    assert summary["false_positive_candidates_total"] == 1
    assert summary["readiness_recommendation"] == "KEEP_DRY_RUN_INSUFFICIENT_DATA"


def test_readiness_recommendation_allows_partial_conservative_activation():
    recommendation = readiness_recommendation(
        total_events=MIN_CALIBRATION_DECISIONS,
        predominant_mode="NORMAL",
        normal_stable=True,
        mode_changes=1,
        mode_change_ratio=0.01,
        false_positive_count=0,
        false_positive_ratio=0.0,
        max_mode_value=1,
        corrupt_lines=0,
        schema_errors=0,
        window_hours=MIN_CALIBRATION_HOURS,
    )

    assert recommendation == "READY_FOR_LIMITED_ENABLEMENT"


def test_missing_audit_file_returns_keep_dry_run(tmp_path):
    report = scheduler_reliability_audit_report(tmp_path / "missing.jsonl")

    assert report["summary"]["total_events"] == 0
    assert report["operational_report"]["recommendation"] == "KEEP_DRY_RUN_INSUFFICIENT_DATA"
    assert report["audit_health"]["file_exists"] is False


def test_empty_audit_file_returns_keep_dry_run(tmp_path):
    audit = tmp_path / "empty.jsonl"
    audit.write_text("", encoding="utf-8")

    report = scheduler_reliability_audit_report(audit)

    assert report["audit_health"]["file_exists"] is True
    assert report["audit_health"]["file_empty"] is True
    assert report["summary"]["total_events"] == 0
    assert report["summary"]["readiness_recommendation"] == "KEEP_DRY_RUN_INSUFFICIENT_DATA"


def test_partial_corruption_blocks_enablement_when_window_is_sufficient(tmp_path):
    audit = tmp_path / "audit.jsonl"
    start = datetime.now(tz=timezone.utc) - timedelta(hours=MIN_CALIBRATION_HOURS + 1)
    events = [
        _audit_event(start + timedelta(minutes=20 * index))
        for index in range(MIN_CALIBRATION_DECISIONS)
    ]
    audit.write_text(
        "\n".join([*(json.dumps(event) for event in events), "broken-json"]),
        encoding="utf-8",
    )

    report = scheduler_reliability_audit_report(audit)

    assert report["audit_health"]["corrupt_lines"] == 1
    assert report["summary"]["readiness_recommendation"] == "DO_NOT_ENABLE_RUNTIME_UNSTABLE"


def test_insufficient_window_keeps_dry_run(tmp_path):
    audit = tmp_path / "audit.jsonl"
    start = datetime.now(tz=timezone.utc) - timedelta(minutes=30)
    _write_events(
        audit,
        [
            _audit_event(start + timedelta(minutes=index))
            for index in range(MIN_CALIBRATION_DECISIONS)
        ],
    )

    report = scheduler_reliability_audit_report(audit)

    assert report["summary"]["total_events"] == MIN_CALIBRATION_DECISIONS
    assert report["summary"]["window_hours"] < MIN_CALIBRATION_HOURS
    assert report["summary"]["readiness_recommendation"] == "KEEP_DRY_RUN_INSUFFICIENT_DATA"


def test_sufficient_stable_window_is_ready_for_limited_enablement(tmp_path):
    audit = tmp_path / "audit.jsonl"
    start = datetime.now(tz=timezone.utc) - timedelta(hours=MIN_CALIBRATION_HOURS + 1)
    _write_events(
        audit,
        [_audit_event(start + timedelta(minutes=20 * index)) for index in range(25)],
    )

    report = scheduler_reliability_audit_report(audit)

    assert report["summary"]["normal_stable"] is True
    assert report["summary"]["readiness_recommendation"] == "READY_FOR_LIMITED_ENABLEMENT"
    assert report["activation_gates"]["readiness"]["passed"] is True


def test_high_false_positive_risk_keeps_dry_run(tmp_path):
    audit = tmp_path / "audit.jsonl"
    start = datetime.now(tz=timezone.utc) - timedelta(hours=MIN_CALIBRATION_HOURS + 1)
    events = [
        _audit_event(start + timedelta(minutes=20 * index))
        for index in range(MIN_CALIBRATION_DECISIONS)
    ]
    events[3] = _audit_event(
        start + timedelta(minutes=60),
        mode="CONSERVATIVE",
        priority="NORMAL",
        job_name="analytics_job",
        batch_size=75,
    )
    _write_events(audit, events)

    report = scheduler_reliability_audit_report(audit)

    assert report["summary"]["false_positive_candidates_total"] == 1
    assert (
        report["summary"]["readiness_recommendation"]
        == "KEEP_DRY_RUN_HIGH_FALSE_POSITIVE_RISK"
    )


def test_last_minutes_filter_keeps_recent_events_only(tmp_path):
    audit = tmp_path / "audit.jsonl"
    now = datetime.now(tz=timezone.utc)
    _write_events(
        audit,
        [
            _audit_event(now - timedelta(minutes=120), job_name="old"),
            _audit_event(now - timedelta(minutes=5), job_name="recent"),
        ],
    )

    report = scheduler_reliability_audit_report(audit, last_minutes=30)

    assert report["summary"]["total_events"] == 1
    assert report["latest_events"][0]["job_name"] == "recent"


def test_scheduler_reliability_audit_endpoint_passes_filters(monkeypatch):
    from app.runtime import api

    captured = {}

    def fake_report(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(api, "scheduler_reliability_audit_report", fake_report)

    response = api.scheduler_reliability_audit(
        last_minutes=30,
        mode="NORMAL",
        job_priority="HIGH",
    )

    assert response == {"ok": True}
    assert captured == {"last_minutes": 30, "mode": "NORMAL", "job_priority": "HIGH"}
