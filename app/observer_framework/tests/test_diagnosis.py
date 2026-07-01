"""Tests for SnapshotDiagnosisEngine — incident detection, recovery plan, validation, certification.

All scenarios operate purely on RuntimeSnapshotContract fixtures — no production
access anywhere in this file.
"""
from __future__ import annotations

from datetime import datetime

from app.observation_engine.contracts import ObservationHealth, ObservationRecord, ObservationSeverity
from app.observer_framework.diagnosis import SnapshotDiagnosisEngine
from app.observer_framework.snapshot_contract import RuntimeSnapshotContract
from app.scientific_identity.contract import stable_hash


def _record(source: str, severity: ObservationSeverity, health: ObservationHealth, **metrics) -> ObservationRecord:
    return ObservationRecord(
        observation_id=stable_hash({"o": source, "sev": severity.value, "h": health.value, "m": metrics}),
        scientific_id=stable_hash({"s": source}),
        lineage_id="lin-1",
        project="poupi-infra",
        domain="GENERIC",
        source=source,
        severity=severity,
        health=health,
        evidence=[],
        metrics=metrics,
        timestamp=datetime(2026, 7, 1, 12, 0, 0),
    )


def _snapshot(records, captured_at="2026-07-01T12:00:00") -> RuntimeSnapshotContract:
    return RuntimeSnapshotContract.create(source="test-fixture", records=records, adapter_health=[], captured_at=captured_at)


def test_healthy_snapshot_has_zero_incidents() -> None:
    snap = _snapshot([_record("postgresql", ObservationSeverity.INFO, ObservationHealth.HEALTHY, x=1.0)])
    diag = SnapshotDiagnosisEngine().diagnose(snap)
    assert diag.incidents == ()
    assert diag.overall_health == "HEALTHY"
    assert diag.overall_severity == "INFO"


def test_degraded_record_raises_incident() -> None:
    snap = _snapshot([_record("postgresql", ObservationSeverity.ERROR, ObservationHealth.DEGRADED, active_connections=98.0)])
    diag = SnapshotDiagnosisEngine().diagnose(snap)
    assert len(diag.incidents) == 1
    inc = diag.incidents[0]
    assert inc.source == "postgresql"
    assert inc.priority == "P1"
    assert "active_connections" in inc.probable_cause


def test_incident_priority_scales_with_severity() -> None:
    snap = _snapshot([_record("redis", ObservationSeverity.CRITICAL, ObservationHealth.CRITICAL)])
    diag = SnapshotDiagnosisEngine().diagnose(snap)
    assert diag.incidents[0].priority == "P0"


def test_incidents_sorted_by_priority() -> None:
    snap = _snapshot([
        _record("redis", ObservationSeverity.WARNING, ObservationHealth.UNKNOWN),
        _record("postgresql", ObservationSeverity.CRITICAL, ObservationHealth.CRITICAL),
    ])
    diag = SnapshotDiagnosisEngine().diagnose(snap)
    assert [i.priority for i in diag.incidents] == ["P0", "P2"]


def test_collectors_missing_lists_ungathered_domains() -> None:
    snap = _snapshot([_record("postgresql", ObservationSeverity.INFO, ObservationHealth.HEALTHY)])
    diag = SnapshotDiagnosisEngine().diagnose(snap)
    assert "postgres" in diag.collectors_present
    assert "specky" in diag.collectors_missing
    assert "coolify" in diag.collectors_missing


def test_recovery_plan_never_executes() -> None:
    snap = _snapshot([_record("redis", ObservationSeverity.CRITICAL, ObservationHealth.CRITICAL)])
    diag = SnapshotDiagnosisEngine().diagnose(snap)
    plan = SnapshotDiagnosisEngine().build_recovery_plan(diag.incidents[0])
    assert plan.executes_changes is False
    assert len(plan.actions) == 4
    assert [a.order for a in plan.actions] == [1, 2, 3, 4]


def test_compare_detects_resolution() -> None:
    engine = SnapshotDiagnosisEngine()
    before = _snapshot([_record("postgresql", ObservationSeverity.ERROR, ObservationHealth.DEGRADED)], "2026-07-01T12:00:00")
    after = _snapshot([_record("postgresql", ObservationSeverity.INFO, ObservationHealth.HEALTHY)], "2026-07-01T13:00:00")
    result = engine.compare(before, after)
    assert result.fully_resolved is True
    assert len(result.resolved_incidents) == 1
    assert result.unresolved_incidents == ()
    assert result.new_incidents == ()


def test_compare_detects_unresolved() -> None:
    engine = SnapshotDiagnosisEngine()
    before = _snapshot([_record("postgresql", ObservationSeverity.ERROR, ObservationHealth.DEGRADED)], "2026-07-01T12:00:00")
    after = _snapshot([_record("postgresql", ObservationSeverity.WARNING, ObservationHealth.DEGRADED)], "2026-07-01T13:00:00")
    result = engine.compare(before, after)
    assert result.fully_resolved is False
    assert len(result.unresolved_incidents) == 1


def test_compare_detects_new_incident() -> None:
    engine = SnapshotDiagnosisEngine()
    before = _snapshot([_record("postgresql", ObservationSeverity.INFO, ObservationHealth.HEALTHY)], "2026-07-01T12:00:00")
    after = _snapshot([
        _record("postgresql", ObservationSeverity.INFO, ObservationHealth.HEALTHY),
        _record("redis", ObservationSeverity.CRITICAL, ObservationHealth.CRITICAL),
    ], "2026-07-01T13:00:00")
    result = engine.compare(before, after)
    assert len(result.new_incidents) == 1


def test_certify_go_when_fully_resolved() -> None:
    engine = SnapshotDiagnosisEngine()
    before = _snapshot([_record("postgresql", ObservationSeverity.ERROR, ObservationHealth.DEGRADED)], "2026-07-01T12:00:00")
    after = _snapshot([_record("postgresql", ObservationSeverity.INFO, ObservationHealth.HEALTHY)], "2026-07-01T13:00:00")
    cert = engine.certify(engine.compare(before, after))
    assert cert.classification == "GO"


def test_certify_go_with_observations_when_unresolved() -> None:
    engine = SnapshotDiagnosisEngine()
    before = _snapshot([_record("postgresql", ObservationSeverity.ERROR, ObservationHealth.DEGRADED)], "2026-07-01T12:00:00")
    after = _snapshot([_record("postgresql", ObservationSeverity.WARNING, ObservationHealth.DEGRADED)], "2026-07-01T13:00:00")
    cert = engine.certify(engine.compare(before, after))
    assert cert.classification == "GO_WITH_OBSERVATIONS"


def test_certify_no_go_when_new_incident() -> None:
    engine = SnapshotDiagnosisEngine()
    before = _snapshot([_record("postgresql", ObservationSeverity.INFO, ObservationHealth.HEALTHY)], "2026-07-01T12:00:00")
    after = _snapshot([
        _record("postgresql", ObservationSeverity.INFO, ObservationHealth.HEALTHY),
        _record("redis", ObservationSeverity.CRITICAL, ObservationHealth.CRITICAL),
    ], "2026-07-01T13:00:00")
    cert = engine.certify(engine.compare(before, after))
    assert cert.classification == "NO_GO"


def test_diagnose_flags_broken_integrity() -> None:
    snap = _snapshot([_record("postgresql", ObservationSeverity.INFO, ObservationHealth.HEALTHY)])
    from dataclasses import replace
    tampered = replace(snap, integrity_hash="0" * 32)
    diag = SnapshotDiagnosisEngine().diagnose(tampered)
    assert diag.integrity_verified is False
    assert diag.validation_errors != ()
