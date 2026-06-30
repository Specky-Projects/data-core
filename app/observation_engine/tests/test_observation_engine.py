"""Tests for ObservationEngine."""
from __future__ import annotations

import uuid

import pytest

from app.capability_orchestrator.contracts import CapabilityKind, CapabilityRequest
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.capability_orchestrator.registry import CapabilityRegistry
from app.observation_engine.adapters.crypto import CryptoAdapter
from app.observation_engine.adapters.mirror import MirrorAdapter
from app.observation_engine.contracts import ObservationHealth, ObservationRecord, ObservationSeverity
from app.observation_engine.engine import ObservationEngine


def _make_orchestrator() -> tuple[CapabilityOrchestrator, ObservationEngine]:
    registry = CapabilityRegistry()
    orch = CapabilityOrchestrator(registry)
    engine = ObservationEngine()
    engine.register(orch)
    return orch, engine


# ── Registration tests ─────────────────────────────────────────────────────────

def test_capabilities_registered() -> None:
    orch, _ = _make_orchestrator()
    ids = orch.registered_ids()
    assert ObservationEngine.CAPABILITY_COLLECT_ALL in ids
    assert ObservationEngine.CAPABILITY_COLLECT_PROJECT in ids
    assert ObservationEngine.CAPABILITY_HEALTH in ids


def test_capabilities_are_observation_kind() -> None:
    orch, _ = _make_orchestrator()
    caps = orch.discover(CapabilityKind.OBSERVATION)
    cap_ids = [c.capability_id for c in caps]
    assert ObservationEngine.CAPABILITY_COLLECT_ALL in cap_ids


# ── Execute tests ──────────────────────────────────────────────────────────────

def test_collect_all_executes() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=ObservationEngine.CAPABILITY_COLLECT_ALL,
        inputs={},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert "records" in resp.outputs
    assert isinstance(resp.outputs["records"], list)
    assert len(resp.outputs["records"]) > 0


def test_collect_all_advisory_only() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=ObservationEngine.CAPABILITY_COLLECT_ALL,
        inputs={},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True


def test_collect_project_filters_correctly() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=ObservationEngine.CAPABILITY_COLLECT_PROJECT,
        inputs={"project": "poupi-crypto"},
        context={},
    )
    resp = orch.execute(req)
    records = resp.outputs["records"]
    for r in records:
        assert r["project"] == "poupi-crypto"


def test_health_capability_returns_adapters() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=ObservationEngine.CAPABILITY_HEALTH,
        inputs={},
        context={},
    )
    resp = orch.execute(req)
    assert "adapters" in resp.outputs
    assert isinstance(resp.outputs["adapters"], list)
    assert len(resp.outputs["adapters"]) > 0


def test_outputs_are_structured_dicts() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=ObservationEngine.CAPABILITY_COLLECT_ALL,
        inputs={},
        context={},
    )
    resp = orch.execute(req)
    for rec in resp.outputs["records"]:
        assert isinstance(rec, dict)
        assert "observation_id" in rec
        assert "project" in rec
        assert "advisory_only" in rec
        assert rec["advisory_only"] is True


# ── Adapter tests ──────────────────────────────────────────────────────────────

def test_crypto_adapter_collect() -> None:
    adapter = CryptoAdapter()
    records = adapter.collect()
    assert len(records) == 1
    rec = records[0]
    assert isinstance(rec, ObservationRecord)
    assert rec.advisory_only is True
    assert rec.project == "poupi-crypto"


def test_mirror_adapter_collect() -> None:
    adapter = MirrorAdapter()
    records = adapter.collect()
    assert len(records) == 1
    assert records[0].advisory_only is True


def test_observation_record_advisory_only_enforced() -> None:
    from datetime import datetime
    with pytest.raises(AssertionError):
        ObservationRecord(
            observation_id="obs-001",
            scientific_id="sci-001",
            lineage_id="lin-001",
            project="test",
            domain="TEST",
            source="test-source",
            severity=ObservationSeverity.INFO,
            health=ObservationHealth.HEALTHY,
            evidence=[],
            metrics={},
            timestamp=datetime.utcnow(),
            advisory_only=False,  # must raise
        )


def test_observation_record_requires_project() -> None:
    from datetime import datetime
    with pytest.raises(AssertionError):
        ObservationRecord(
            observation_id="obs-001",
            scientific_id="sci-001",
            lineage_id="lin-001",
            project="",  # must raise
            domain="TEST",
            source="test-source",
            severity=ObservationSeverity.INFO,
            health=ObservationHealth.HEALTHY,
            evidence=[],
            metrics={},
            timestamp=datetime.utcnow(),
        )


def test_engine_collect_all_multiple_adapters() -> None:
    _, engine = _make_orchestrator()
    records = engine.collect_all()
    projects = {r.project for r in records}
    # At least 2 different projects must appear
    assert len(projects) >= 2


def test_engine_isolation_does_not_call_other_engines() -> None:
    """Observation Engine must not import or call other engines."""
    import app.observation_engine.engine as mod
    src = open(mod.__file__).read()
    for forbidden in ["intelligence_engine", "development_engine", "research_engine",
                      "optimization_engine", "knowledge_engine", "decision_engine"]:
        assert forbidden not in src, f"ObservationEngine must not reference {forbidden}"
