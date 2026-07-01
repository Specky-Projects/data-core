"""Tests for RuntimeSnapshotContract — determinism, integrity, JSON round-trip."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from app.observation_engine.contracts import ObservationHealth, ObservationRecord, ObservationSeverity
from app.observer_framework.snapshot_contract import (
    ObservationRecordSnapshot,
    RuntimeSnapshotContract,
)
from app.scientific_identity.contract import stable_hash


def _record(source: str = "postgresql", **overrides) -> ObservationRecord:
    base = dict(
        observation_id=stable_hash({"o": source}),
        scientific_id=stable_hash({"s": source}),
        lineage_id="lin-1",
        project="poupi-infra",
        domain="GENERIC",
        source=source,
        severity=ObservationSeverity.INFO,
        health=ObservationHealth.HEALTHY,
        evidence=[],
        metrics={"x": 1.0},
        timestamp=datetime(2026, 7, 1, 12, 0, 0),
    )
    base.update(overrides)
    return ObservationRecord(**base)


def test_create_is_deterministic_for_identical_input() -> None:
    a = RuntimeSnapshotContract.create(source="s", records=[_record()], adapter_health=[], captured_at="2026-07-01T00:00:00")
    b = RuntimeSnapshotContract.create(source="s", records=[_record()], adapter_health=[], captured_at="2026-07-01T00:00:00")
    assert a.snapshot_id == b.snapshot_id
    assert a.integrity_hash == b.integrity_hash


def test_snapshot_id_differs_for_different_content_same_timestamp() -> None:
    """Regression: snapshot_id must incorporate content, not just (source, captured_at)."""
    a = RuntimeSnapshotContract.create(
        source="s", records=[_record(metrics={"x": 1.0})], adapter_health=[], captured_at="2026-07-01T00:00:00"
    )
    b = RuntimeSnapshotContract.create(
        source="s", records=[_record(metrics={"x": 2.0})], adapter_health=[], captured_at="2026-07-01T00:00:00"
    )
    assert a.snapshot_id != b.snapshot_id


def test_verify_integrity_true_for_untampered_snapshot() -> None:
    snap = RuntimeSnapshotContract.create(source="s", records=[_record()], adapter_health=[])
    assert snap.verify_integrity() is True
    assert snap.validate() == []


def test_verify_integrity_false_after_tampering() -> None:
    snap = RuntimeSnapshotContract.create(source="s", records=[_record()], adapter_health=[])
    tampered = RuntimeSnapshotContract(
        snapshot_id=snap.snapshot_id,
        captured_at=snap.captured_at,
        schema_version=snap.schema_version,
        source=snap.source,
        records=(ObservationRecordSnapshot.from_dict({**snap.records[0].to_dict(), "severity": "CRITICAL"}),),
        adapter_health=snap.adapter_health,
        integrity_hash=snap.integrity_hash,  # stale — payload changed, hash didn't
    )
    assert tampered.verify_integrity() is False
    assert any("integrity_hash" in e for e in tampered.validate())


def test_json_round_trip_preserves_integrity() -> None:
    snap = RuntimeSnapshotContract.create(source="s", records=[_record(), _record(source="redis")], adapter_health=[{"adapter": "postgres", "status": "HEALTHY", "detail": {}}])
    raw = json.dumps(snap.to_dict())
    restored = RuntimeSnapshotContract.from_dict(json.loads(raw))
    assert restored.snapshot_id == snap.snapshot_id
    assert restored.verify_integrity() is True
    assert restored.collectors_present() == snap.collectors_present()


def test_worst_severity_and_health() -> None:
    snap = RuntimeSnapshotContract.create(
        source="s",
        records=[
            _record(source="a", severity=ObservationSeverity.INFO, health=ObservationHealth.HEALTHY),
            _record(source="b", severity=ObservationSeverity.CRITICAL, health=ObservationHealth.CRITICAL),
        ],
        adapter_health=[],
    )
    assert snap.worst_severity() is ObservationSeverity.CRITICAL
    assert snap.worst_health() is ObservationHealth.CRITICAL


def test_empty_snapshot_worst_values_none() -> None:
    snap = RuntimeSnapshotContract.create(source="s", records=[], adapter_health=[])
    assert snap.worst_severity() is None
    assert snap.worst_health() is None


def test_by_source_filters() -> None:
    snap = RuntimeSnapshotContract.create(source="s", records=[_record(source="a"), _record(source="b")], adapter_health=[])
    assert len(snap.by_source("a")) == 1
    assert len(snap.by_source("nonexistent")) == 0


def test_advisory_only_enforced_on_record_validate() -> None:
    bad = ObservationRecordSnapshot.from_dict({**_record().__dict__, "advisory_only": False} if False else {
        "observation_id": "x", "scientific_id": "y", "lineage_id": "z", "project": "p", "domain": "d",
        "source": "s", "severity": "INFO", "health": "HEALTHY", "evidence": [], "metrics": {},
        "timestamp": "2026-07-01T00:00:00", "advisory_only": False, "version": "v1",
    })
    assert any("advisory_only" in e for e in bad.validate())
