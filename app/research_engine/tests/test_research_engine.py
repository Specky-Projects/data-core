"""Tests for ResearchEngine."""
from __future__ import annotations

import uuid

import pytest

from app.capability_orchestrator.contracts import CapabilityKind, CapabilityRequest
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.capability_orchestrator.registry import CapabilityRegistry
from app.research_engine.cache import ResearchCache
from app.research_engine.contracts import ResearchKind, ResearchResult
from app.research_engine.engine import ResearchEngine


def _make_orchestrator() -> tuple[CapabilityOrchestrator, ResearchEngine]:
    registry = CapabilityRegistry()
    orch = CapabilityOrchestrator(registry)
    engine = ResearchEngine()
    engine.register(orch)
    return orch, engine


# ── Registration ───────────────────────────────────────────────────────────────

def test_all_capabilities_registered() -> None:
    orch, _ = _make_orchestrator()
    ids = orch.registered_ids()
    assert ResearchEngine.CAPABILITY_COMPARATIVE in ids
    assert ResearchEngine.CAPABILITY_ARCHITECTURE in ids
    assert ResearchEngine.CAPABILITY_TECHNOLOGY in ids
    assert ResearchEngine.CAPABILITY_OPPORTUNITY in ids
    assert ResearchEngine.CAPABILITY_COMPETITIVE in ids
    assert ResearchEngine.CAPABILITY_SCIENTIFIC in ids
    assert ResearchEngine.CAPABILITY_TREND in ids


def test_capabilities_are_research_kind() -> None:
    orch, _ = _make_orchestrator()
    caps = orch.discover(CapabilityKind.RESEARCH)
    assert len(caps) == 7


# ── Execution ─────────────────────────────────────────────────────────────────

def test_comparative_executes() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=ResearchEngine.CAPABILITY_COMPARATIVE,
        inputs={"options": ["postgres", "mysql"]},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert "findings" in resp.outputs
    assert isinstance(resp.outputs["findings"], list)


def test_all_research_capabilities_execute() -> None:
    orch, _ = _make_orchestrator()
    for cap_id in [
        ResearchEngine.CAPABILITY_COMPARATIVE,
        ResearchEngine.CAPABILITY_ARCHITECTURE,
        ResearchEngine.CAPABILITY_TECHNOLOGY,
        ResearchEngine.CAPABILITY_OPPORTUNITY,
        ResearchEngine.CAPABILITY_COMPETITIVE,
        ResearchEngine.CAPABILITY_SCIENTIFIC,
        ResearchEngine.CAPABILITY_TREND,
    ]:
        req = CapabilityRequest(
            request_id=str(uuid.uuid4()),
            capability_id=cap_id,
            inputs={},
            context={},
        )
        resp = orch.execute(req)
        assert resp.advisory_only is True, f"advisory_only failed for {cap_id}"
        assert isinstance(resp.outputs, dict), f"outputs not dict for {cap_id}"


def test_research_result_advisory_only_enforced() -> None:
    with pytest.raises(AssertionError):
        ResearchResult(
            result_id="r",
            kind=ResearchKind.COMPARATIVE,
            findings=[],
            summary="test",
            confidence=0.5,
            sources=[],
            advisory_only=False,
        )


def test_research_result_confidence_range() -> None:
    with pytest.raises(AssertionError):
        ResearchResult(
            result_id="r",
            kind=ResearchKind.COMPARATIVE,
            findings=[],
            summary="test",
            confidence=1.5,  # invalid
            sources=[],
            advisory_only=True,
        )


# ── Cache ──────────────────────────────────────────────────────────────────────

def test_research_cache_stores_and_retrieves() -> None:
    cache = ResearchCache()
    result = ResearchResult(
        result_id="r1",
        kind=ResearchKind.TREND,
        findings=[],
        summary="test",
        confidence=0.7,
        sources=[],
        advisory_only=True,
    )
    cache.set("trend", {"topic": "ai"}, result)
    retrieved = cache.get("trend", {"topic": "ai"})
    assert retrieved is result


def test_research_cache_miss_returns_none() -> None:
    cache = ResearchCache()
    assert cache.get("trend", {"topic": "ai"}) is None


def test_research_cache_different_inputs_separate_entries() -> None:
    cache = ResearchCache()
    r1 = ResearchResult("r1", ResearchKind.TREND, [], "a", 0.5, [], advisory_only=True)
    r2 = ResearchResult("r2", ResearchKind.TREND, [], "b", 0.6, [], advisory_only=True)
    cache.set("trend", {"topic": "ai"}, r1)
    cache.set("trend", {"topic": "crypto"}, r2)
    assert cache.size() == 2
    assert cache.get("trend", {"topic": "ai"}) is r1
    assert cache.get("trend", {"topic": "crypto"}) is r2


def test_engine_isolation() -> None:
    import app.research_engine.engine as mod
    src = open(mod.__file__).read()
    for forbidden in ["intelligence_engine", "observation_engine", "development_engine",
                      "optimization_engine", "knowledge_engine", "decision_engine"]:
        assert forbidden not in src
