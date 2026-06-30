"""Tests for DecisionEngine."""
from __future__ import annotations

import uuid

import pytest

from app.capability_orchestrator.contracts import CapabilityKind, CapabilityRequest
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.capability_orchestrator.registry import CapabilityRegistry
from app.decision_engine.contracts import DecisionKind, DecisionResult, PolicyEvaluator
from app.decision_engine.engine import DecisionEngine


def _make_orchestrator() -> tuple[CapabilityOrchestrator, DecisionEngine]:
    registry = CapabilityRegistry()
    orch = CapabilityOrchestrator(registry)
    engine = DecisionEngine()
    engine.register(orch)
    return orch, engine


# ── Registration ───────────────────────────────────────────────────────────────

def test_capabilities_registered() -> None:
    orch, _ = _make_orchestrator()
    ids = orch.registered_ids()
    assert DecisionEngine.CAPABILITY_DECIDE in ids
    assert DecisionEngine.CAPABILITY_EVALUATE_POLICY in ids


def test_capabilities_are_decision_kind() -> None:
    orch, _ = _make_orchestrator()
    caps = orch.discover(CapabilityKind.DECISION)
    assert len(caps) == 2


# ── DecisionResult contract ────────────────────────────────────────────────────

def test_decision_result_advisory_only_enforced() -> None:
    with pytest.raises(AssertionError):
        DecisionResult(
            decision_id="d-001",
            scientific_id="sci-001",
            lineage_id="lin-001",
            decision=DecisionKind.ACT,
            rationale="test",
            confidence=0.8,
            evidence=[],
            advisory_only=False,  # must raise
        )


def test_decision_result_confidence_range() -> None:
    with pytest.raises(AssertionError):
        DecisionResult(
            decision_id="d-001",
            scientific_id="sci-001",
            lineage_id="lin-001",
            decision=DecisionKind.ACT,
            rationale="test",
            confidence=1.5,  # invalid
            evidence=[],
            advisory_only=True,
        )


# ── PolicyEvaluator ────────────────────────────────────────────────────────────

def test_policy_acts_on_high_confidence() -> None:
    policy = PolicyEvaluator()
    kind = policy.evaluate({"confidence": 0.9}, [], threshold=0.7)
    assert kind == DecisionKind.ACT


def test_policy_defers_on_borderline_confidence() -> None:
    policy = PolicyEvaluator()
    kind = policy.evaluate({"confidence": 0.55}, [], threshold=0.7)
    assert kind == DecisionKind.DEFER


def test_policy_dont_act_on_low_confidence() -> None:
    policy = PolicyEvaluator()
    kind = policy.evaluate({"confidence": 0.2}, [], threshold=0.7)
    assert kind == DecisionKind.DONT_ACT


def test_policy_investigates_on_critical_health() -> None:
    policy = PolicyEvaluator()
    kind = policy.evaluate({"confidence": 0.9, "health": "CRITICAL"}, [], threshold=0.7)
    assert kind == DecisionKind.INVESTIGATE


# ── Engine execution ───────────────────────────────────────────────────────────

def test_decide_capability_executes() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=DecisionEngine.CAPABILITY_DECIDE,
        inputs={"context": {"confidence": 0.85}, "evidence": ["obs-001"]},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert "decision" in resp.outputs
    assert isinstance(resp.outputs["decision"], str)


def test_decide_advisory_only_always_true() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=DecisionEngine.CAPABILITY_DECIDE,
        inputs={"context": {"confidence": 0.95}, "evidence": []},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert resp.outputs["advisory_only"] is True


def test_decide_outputs_are_structured() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=DecisionEngine.CAPABILITY_DECIDE,
        inputs={"context": {"confidence": 0.5}, "evidence": []},
        context={},
    )
    resp = orch.execute(req)
    assert isinstance(resp.outputs, dict)
    assert "decision" in resp.outputs
    assert "rationale" in resp.outputs
    assert "confidence" in resp.outputs
    # Never a bare string at top level
    assert not isinstance(resp.outputs, str)


def test_evaluate_policy_capability_executes() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=DecisionEngine.CAPABILITY_EVALUATE_POLICY,
        inputs={"context": {"confidence": 0.3, "health": "HEALTHY"}, "evidence": []},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert resp.outputs["decision"] == str(DecisionKind.DONT_ACT)


def test_engine_isolation() -> None:
    import app.decision_engine.engine as mod
    src = open(mod.__file__).read()
    for forbidden in ["intelligence_engine", "observation_engine", "development_engine",
                      "research_engine", "optimization_engine", "knowledge_engine"]:
        assert forbidden not in src
