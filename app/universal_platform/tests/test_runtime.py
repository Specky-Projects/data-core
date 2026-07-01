"""Tests for the Universal Observation Runtime (WS5) — reuse, determinism, replay, coverage, snapshot."""
from __future__ import annotations

import pytest

from app.scientific_consumers.runtime import ScientificConsumerRuntime
from app.universal_platform.events import Severity, UniversalEvent, to_decision_facts
from app.universal_platform.runtime import (
    COVERAGE_ARTIFACTS,
    UniversalObservationRuntime,
)


def _event(**overrides) -> UniversalEvent:
    base = dict(
        project="infrastructure",
        domain="INFRASTRUCTURE",
        event_type="redis.restart",
        entity_id="redis-01",
        occurred_at="2026-06-30T10:00:00Z",
        confidence=1.0,
        severity="HIGH",
        evidence=[{"evidence_id": "e1", "source_name": "coolify", "source_type": "PLATFORM", "evidence_level": "VERIFIED"}],
        metrics={"restarts": 3},
    )
    base.update(overrides)
    return UniversalEvent.create(**base)


def test_runtime_reuses_scientific_consumer_runtime() -> None:
    """The universal runtime must not re-implement the chain — it wraps the Phase 1 one."""
    inner = ScientificConsumerRuntime()
    runtime = UniversalObservationRuntime(runtime=inner)
    assert runtime.runtime is inner


def test_observe_produces_full_coverage() -> None:
    record = UniversalObservationRuntime().observe(_event())
    assert record.coverage.coverage_ratio == 1.0
    assert record.coverage.is_complete is True
    assert record.coverage.missing == ()
    assert set(record.coverage.present) == set(COVERAGE_ARTIFACTS)


def test_observe_has_no_validation_errors() -> None:
    record = UniversalObservationRuntime().observe(_event())
    assert record.coverage.validation_errors == ()
    assert record.scientific.validate() == []


def test_all_nine_artifacts_present() -> None:
    record = UniversalObservationRuntime().observe(_event())
    assert record.observation is not None
    assert record.scientific.identity_chain is not None
    assert record.scientific.pipeline_trace is not None
    assert record.scientific.explainability is not None
    assert record.scientific.replay_manifest is not None
    assert record.scientific.ledger is not None
    assert record.learning_feed["evidence"] is not None
    assert record.coverage is not None
    assert record.audit is not None


def test_determinism_same_event_same_hashes() -> None:
    runtime = UniversalObservationRuntime()
    a = runtime.observe(_event())
    b = runtime.observe(_event())
    assert a.observation.observation_id == b.observation.observation_id
    assert a.observation.payload_hash == b.observation.payload_hash
    assert a.audit.record_hash == b.audit.record_hash
    assert a.pipeline_id == b.pipeline_id


def test_replay_manifest_reconstructs_identically() -> None:
    record = UniversalObservationRuntime().observe(_event())
    pipeline = ScientificConsumerRuntime().pipeline
    replayed = pipeline.replay(record.scientific.replay_manifest)
    original_hashes = [s.output_hash for s in record.scientific.pipeline_trace.stages]
    replayed_trace = pipeline.trace(replayed.context.pipeline_id)
    assert replayed_trace is not None
    replayed_hashes = [s.output_hash for s in replayed_trace.stages]
    assert original_hashes == replayed_hashes


def test_audit_snapshot_verifies_observation() -> None:
    record = UniversalObservationRuntime().observe(_event())
    assert record.audit.verify(record.observation) is True


def test_coverage_helper_matches_observe() -> None:
    runtime = UniversalObservationRuntime()
    ev = _event()
    assert runtime.coverage(ev).as_dict() == runtime.observe(ev).coverage.as_dict()


def test_snapshot_helper_matches_observe() -> None:
    runtime = UniversalObservationRuntime()
    ev = _event()
    assert runtime.snapshot(ev).snapshot_id == runtime.observe(ev).audit.snapshot_id


def test_invalid_event_rejected() -> None:
    bad = UniversalEvent.create(
        project="", domain="X", event_type="t", entity_id="e", occurred_at="2026-06-30T00:00:00Z"
    )
    with pytest.raises(ValueError, match="invalid UniversalEvent"):
        UniversalObservationRuntime().observe(bad)


def test_record_is_advisory_shadow_readonly() -> None:
    record = UniversalObservationRuntime().observe(_event())
    assert record.advisory_only is True
    assert record.shadow_mode is True
    assert record.read_only is True


def test_to_decision_facts_is_neutral_not_a_verdict() -> None:
    facts = to_decision_facts(_event(confidence=0.8))
    assert facts.verdict == "OBSERVED"
    assert facts.action == "OBSERVE"
    assert facts.prior == 0.5
    assert facts.committee_verdict == "ABSTAIN"
    assert facts.simulation_only is True
    assert facts.posterior == pytest.approx(0.8)


def test_severity_enum_ordering() -> None:
    assert Severity.CRITICAL.rank > Severity.HIGH.rank > Severity.MEDIUM.rank
    assert Severity.MEDIUM.rank > Severity.LOW.rank > Severity.INFO.rank
