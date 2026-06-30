"""Tests for OptimizationEngine."""
from __future__ import annotations

import uuid

import pytest

from app.capability_orchestrator.contracts import CapabilityKind, CapabilityRequest
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.capability_orchestrator.registry import CapabilityRegistry
from app.optimization_engine.contracts import OptimizationStep
from app.optimization_engine.engine import OptimizationEngine
from app.optimization_engine.priority_matrix import PriorityMatrix


def _make_orchestrator() -> tuple[CapabilityOrchestrator, OptimizationEngine]:
    registry = CapabilityRegistry()
    orch = CapabilityOrchestrator(registry)
    engine = OptimizationEngine()
    engine.register(orch)
    return orch, engine


def _make_step(
    impact: str = "HIGH",
    effort: str = "LOW",
    risk: str = "LOW",
) -> OptimizationStep:
    return OptimizationStep(
        step_id=str(uuid.uuid4()),
        title="Test step",
        description="Test",
        effort=effort,
        impact=impact,
        risk=risk,
        estimated_gain="10%",
        rollback_procedure="git revert",
        validation_steps=["check health"],
        advisory_only=True,
    )


# ── Registration ───────────────────────────────────────────────────────────────

def test_all_capabilities_registered() -> None:
    orch, _ = _make_orchestrator()
    ids = orch.registered_ids()
    assert OptimizationEngine.CAPABILITY_INFRA in ids
    assert OptimizationEngine.CAPABILITY_DATABASE in ids
    assert OptimizationEngine.CAPABILITY_CACHE in ids
    assert OptimizationEngine.CAPABILITY_AI_COST in ids
    assert OptimizationEngine.CAPABILITY_LATENCY in ids
    assert OptimizationEngine.CAPABILITY_ARCHITECTURE in ids
    assert OptimizationEngine.CAPABILITY_COST in ids
    assert OptimizationEngine.CAPABILITY_PRIORITIZE in ids


def test_capabilities_are_optimization_kind() -> None:
    orch, _ = _make_orchestrator()
    caps = orch.discover(CapabilityKind.OPTIMIZATION)
    assert len(caps) == 8


# ── OptimizationStep constraints ──────────────────────────────────────────────

def test_step_rollback_required() -> None:
    with pytest.raises(AssertionError, match="rollback_procedure"):
        OptimizationStep(
            step_id="s1",
            title="T",
            description="D",
            effort="LOW",
            impact="HIGH",
            risk="LOW",
            estimated_gain="10%",
            rollback_procedure="",  # must raise
            validation_steps=[],
            advisory_only=True,
        )


def test_step_advisory_only_enforced() -> None:
    with pytest.raises(AssertionError):
        OptimizationStep(
            step_id="s1",
            title="T",
            description="D",
            effort="LOW",
            impact="HIGH",
            risk="LOW",
            estimated_gain="10%",
            rollback_procedure="revert",
            validation_steps=[],
            advisory_only=False,
        )


def test_step_invalid_effort_raises() -> None:
    with pytest.raises(AssertionError):
        OptimizationStep(
            step_id="s1",
            title="T",
            description="D",
            effort="EXTREME",  # invalid
            impact="HIGH",
            risk="LOW",
            estimated_gain="10%",
            rollback_procedure="revert",
            validation_steps=[],
            advisory_only=True,
        )


# ── PriorityMatrix ─────────────────────────────────────────────────────────────

def test_priority_matrix_score_critical_high() -> None:
    matrix = PriorityMatrix()
    step = _make_step(impact="CRITICAL", effort="LOW", risk="LOW")
    score = matrix.score(step)
    assert score > 0


def test_priority_matrix_higher_impact_scores_higher() -> None:
    matrix = PriorityMatrix()
    low = _make_step(impact="LOW", effort="LOW", risk="LOW")
    high = _make_step(impact="HIGH", effort="LOW", risk="LOW")
    assert matrix.score(high) > matrix.score(low)


def test_priority_matrix_higher_risk_scores_lower() -> None:
    matrix = PriorityMatrix()
    safe = _make_step(impact="HIGH", effort="LOW", risk="LOW")
    risky = _make_step(impact="HIGH", effort="LOW", risk="HIGH")
    assert matrix.score(safe) > matrix.score(risky)


def test_priority_matrix_prioritize_sorts_descending() -> None:
    matrix = PriorityMatrix()
    steps = [
        _make_step(impact="LOW", effort="HIGH", risk="HIGH"),
        _make_step(impact="CRITICAL", effort="LOW", risk="LOW"),
        _make_step(impact="MEDIUM", effort="MEDIUM", risk="LOW"),
    ]
    result = matrix.prioritize(steps)
    scores = [matrix.score(s) for s in result]
    assert scores == sorted(scores, reverse=True)


# ── Engine execution ───────────────────────────────────────────────────────────

def test_infra_capability_executes() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=OptimizationEngine.CAPABILITY_INFRA,
        inputs={},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert "steps" in resp.outputs
    assert len(resp.outputs["steps"]) > 0


def test_prioritize_returns_all_steps() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=OptimizationEngine.CAPABILITY_PRIORITIZE,
        inputs={},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert resp.outputs["total"] >= 7  # at least one step per optimizer


def test_all_step_outputs_have_rollback() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=OptimizationEngine.CAPABILITY_PRIORITIZE,
        inputs={},
        context={},
    )
    resp = orch.execute(req)
    for step in resp.outputs["steps"]:
        assert step["rollback_procedure"], f"Missing rollback for step: {step['title']}"


def test_all_optimization_outputs_are_advisory_only() -> None:
    orch, _ = _make_orchestrator()
    for cap_id in [
        OptimizationEngine.CAPABILITY_INFRA,
        OptimizationEngine.CAPABILITY_DATABASE,
        OptimizationEngine.CAPABILITY_CACHE,
        OptimizationEngine.CAPABILITY_AI_COST,
        OptimizationEngine.CAPABILITY_LATENCY,
        OptimizationEngine.CAPABILITY_ARCHITECTURE,
        OptimizationEngine.CAPABILITY_COST,
    ]:
        req = CapabilityRequest(
            request_id=str(uuid.uuid4()),
            capability_id=cap_id,
            inputs={},
            context={},
        )
        resp = orch.execute(req)
        assert resp.advisory_only is True
        assert resp.outputs["advisory_only"] is True


def test_engine_isolation() -> None:
    import app.optimization_engine.engine as mod
    src = open(mod.__file__).read()
    for forbidden in ["intelligence_engine", "observation_engine", "development_engine",
                      "research_engine", "knowledge_engine", "decision_engine"]:
        assert forbidden not in src
