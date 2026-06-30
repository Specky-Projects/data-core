"""Tests for IntelligenceEngine."""
from __future__ import annotations

import uuid

import pytest

from app.capability_orchestrator.contracts import CapabilityKind, CapabilityRequest
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.capability_orchestrator.registry import CapabilityRegistry
from app.intelligence_engine.contracts import (
    AISpecialistKind,
    IntelligenceRequest,
    IntelligenceResult,
)
from app.intelligence_engine.engine import IntelligenceEngine
from app.intelligence_engine.router import IntelligenceRouter
from app.intelligence_engine.specialists.mock import MockAISpecialist


def _make_orchestrator() -> tuple[CapabilityOrchestrator, IntelligenceEngine]:
    registry = CapabilityRegistry()
    orch = CapabilityOrchestrator(registry)
    engine = IntelligenceEngine()
    engine.register(orch)
    return orch, engine


# ── Registration tests ─────────────────────────────────────────────────────────

def test_capabilities_registered() -> None:
    orch, _ = _make_orchestrator()
    ids = orch.registered_ids()
    assert IntelligenceEngine.CAPABILITY_ANALYZE in ids
    assert IntelligenceEngine.CAPABILITY_DIAGNOSE in ids
    assert IntelligenceEngine.CAPABILITY_ARCHITECTURE in ids


def test_capabilities_are_intelligence_kind() -> None:
    orch, _ = _make_orchestrator()
    caps = orch.discover(CapabilityKind.INTELLIGENCE)
    assert len(caps) >= 3


# ── Execution tests ────────────────────────────────────────────────────────────

def test_analyze_executes() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=IntelligenceEngine.CAPABILITY_ANALYZE,
        inputs={"specialist_kind": "DIAGNOSTICS", "observations": []},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert isinstance(resp.outputs, dict)
    assert "analysis" in resp.outputs


def test_diagnose_executes() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=IntelligenceEngine.CAPABILITY_DIAGNOSE,
        inputs={"observations": []},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert "analysis" in resp.outputs
    assert "root_cause" in resp.outputs["analysis"]


def test_architecture_executes() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=IntelligenceEngine.CAPABILITY_ARCHITECTURE,
        inputs={"observations": []},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert "findings" in resp.outputs["analysis"]


def test_advisory_only_enforced() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=IntelligenceEngine.CAPABILITY_ANALYZE,
        inputs={"specialist_kind": "SECURITY", "observations": []},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True


def test_outputs_are_structured_dict() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=IntelligenceEngine.CAPABILITY_ANALYZE,
        inputs={"specialist_kind": "ANOMALY", "observations": []},
        context={},
    )
    resp = orch.execute(req)
    assert isinstance(resp.outputs, dict)
    assert isinstance(resp.outputs["analysis"], dict)
    # NEVER a bare string
    assert not isinstance(resp.outputs["analysis"], str)


# ── MockAISpecialist tests ─────────────────────────────────────────────────────

def test_mock_specialist_diagnostics() -> None:
    specialist = MockAISpecialist()
    req = IntelligenceRequest(
        request_id=str(uuid.uuid4()),
        specialist_kind=AISpecialistKind.DIAGNOSTICS,
        context={},
        observations=[],
    )
    result = specialist.analyze(req)
    assert result.advisory_only is True
    assert isinstance(result.analysis, dict)
    assert "root_cause" in result.analysis


def test_mock_specialist_all_kinds_return_dict() -> None:
    specialist = MockAISpecialist()
    for kind in AISpecialistKind:
        req = IntelligenceRequest(
            request_id=str(uuid.uuid4()),
            specialist_kind=kind,
            context={},
            observations=[],
        )
        result = specialist.analyze(req)
        assert isinstance(result.analysis, dict), f"Expected dict for {kind}"
        assert result.advisory_only is True


def test_intelligence_result_advisory_only_enforced() -> None:
    with pytest.raises(AssertionError):
        IntelligenceResult(
            result_id="r",
            request_id="req",
            specialist_kind=AISpecialistKind.DIAGNOSTICS,
            analysis={"x": 1},
            confidence=0.8,
            evidence=[],
            recommendations=[],
            advisory_only=False,  # must raise
        )


def test_intelligence_result_analysis_must_be_dict() -> None:
    with pytest.raises(AssertionError):
        IntelligenceResult(
            result_id="r",
            request_id="req",
            specialist_kind=AISpecialistKind.DIAGNOSTICS,
            analysis="bare string",  # type: ignore
            confidence=0.8,
            evidence=[],
            recommendations=[],
            advisory_only=True,
        )


def test_router_routes_correctly() -> None:
    router = IntelligenceRouter()
    req = IntelligenceRequest(
        request_id=str(uuid.uuid4()),
        specialist_kind=AISpecialistKind.SECURITY,
        context={},
        observations=[],
    )
    result = router.route(req)
    assert result.specialist_kind == AISpecialistKind.SECURITY
    assert isinstance(result.analysis, dict)


def test_engine_isolation() -> None:
    import app.intelligence_engine.engine as mod
    src = open(mod.__file__).read()
    for forbidden in ["observation_engine", "development_engine", "research_engine",
                      "optimization_engine", "knowledge_engine", "decision_engine"]:
        assert forbidden not in src
