"""Tests for DevelopmentEngine."""
from __future__ import annotations

import uuid

import pytest

from app.capability_orchestrator.contracts import CapabilityKind, CapabilityRequest
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.capability_orchestrator.registry import CapabilityRegistry
from app.development_engine.capabilities.reuse_checker import ReuseCheckerCapability
from app.development_engine.contracts import ReuseAction, ReuseCheckResult
from app.development_engine.engine import DevelopmentEngine


def _make_orchestrator() -> tuple[CapabilityOrchestrator, DevelopmentEngine]:
    registry = CapabilityRegistry()
    orch = CapabilityOrchestrator(registry)
    engine = DevelopmentEngine()
    engine.register(orch)
    return orch, engine


# ── Registration ───────────────────────────────────────────────────────────────

def test_all_capabilities_registered() -> None:
    orch, _ = _make_orchestrator()
    ids = orch.registered_ids()
    assert DevelopmentEngine.CAPABILITY_REUSE_CHECK in ids
    assert DevelopmentEngine.CAPABILITY_ARCH_REVIEW in ids
    assert DevelopmentEngine.CAPABILITY_TECH_DEBT in ids
    assert DevelopmentEngine.CAPABILITY_ADR in ids
    assert DevelopmentEngine.CAPABILITY_SPEC in ids
    assert DevelopmentEngine.CAPABILITY_MIGRATION in ids
    assert DevelopmentEngine.CAPABILITY_TEST_PLAN in ids
    assert DevelopmentEngine.CAPABILITY_DOC in ids
    assert DevelopmentEngine.CAPABILITY_ROADMAP in ids


def test_capabilities_are_development_kind() -> None:
    orch, _ = _make_orchestrator()
    caps = orch.discover(CapabilityKind.DEVELOPMENT)
    assert len(caps) == 9


# ── ReuseChecker ──────────────────────────────────────────────────────────────

def test_reuse_checker_finds_stable_hash() -> None:
    checker = ReuseCheckerCapability()
    result = checker.execute({"concept": "stable_hash"})
    assert result["action"] == str(ReuseAction.REUSE)
    assert len(result["candidates"]) > 0


def test_reuse_checker_unknown_concept_creates_new() -> None:
    checker = ReuseCheckerCapability()
    result = checker.execute({"concept": "completely_new_concept_xyz"})
    assert result["action"] == str(ReuseAction.CREATE_NEW)
    assert result["candidates"] == []


def test_reuse_check_result_advisory_only_enforced() -> None:
    with pytest.raises(AssertionError):
        ReuseCheckResult(
            action=ReuseAction.REUSE,
            candidates=[],
            rationale="test",
            evidence=[],
            advisory_only=False,
        )


# ── Engine execution ───────────────────────────────────────────────────────────

def test_reuse_check_capability_executes() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=DevelopmentEngine.CAPABILITY_REUSE_CHECK,
        inputs={"concept": "observation"},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert "action" in resp.outputs


def test_arch_review_executes() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=DevelopmentEngine.CAPABILITY_ARCH_REVIEW,
        inputs={},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert "findings" in resp.outputs


def test_tech_debt_executes() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=DevelopmentEngine.CAPABILITY_TECH_DEBT,
        inputs={},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert "debt_items" in resp.outputs


def test_adr_executes() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=DevelopmentEngine.CAPABILITY_ADR,
        inputs={"title": "Use advisory_only", "context": "All engines", "decision": "advisory=True"},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert "adr" in resp.outputs


def test_all_outputs_are_dicts() -> None:
    orch, _ = _make_orchestrator()
    for cap_id in [
        DevelopmentEngine.CAPABILITY_REUSE_CHECK,
        DevelopmentEngine.CAPABILITY_ARCH_REVIEW,
        DevelopmentEngine.CAPABILITY_TECH_DEBT,
        DevelopmentEngine.CAPABILITY_ADR,
        DevelopmentEngine.CAPABILITY_SPEC,
        DevelopmentEngine.CAPABILITY_MIGRATION,
        DevelopmentEngine.CAPABILITY_TEST_PLAN,
        DevelopmentEngine.CAPABILITY_DOC,
        DevelopmentEngine.CAPABILITY_ROADMAP,
    ]:
        req = CapabilityRequest(
            request_id=str(uuid.uuid4()),
            capability_id=cap_id,
            inputs={},
            context={},
        )
        resp = orch.execute(req)
        assert isinstance(resp.outputs, dict), f"Expected dict for {cap_id}"
        assert resp.advisory_only is True


def test_advisory_only_in_all_outputs() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=DevelopmentEngine.CAPABILITY_ROADMAP,
        inputs={},
        context={},
    )
    resp = orch.execute(req)
    assert resp.outputs.get("advisory_only") is True


def test_engine_isolation() -> None:
    import app.development_engine.engine as mod
    src = open(mod.__file__).read()
    for forbidden in ["intelligence_engine", "observation_engine", "research_engine",
                      "optimization_engine", "knowledge_engine", "decision_engine"]:
        assert forbidden not in src
