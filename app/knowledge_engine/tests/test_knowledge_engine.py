"""Tests for KnowledgeEngine."""
from __future__ import annotations

import uuid

import pytest

from app.capability_orchestrator.contracts import CapabilityKind, CapabilityRequest
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.capability_orchestrator.registry import CapabilityRegistry
from app.knowledge_engine.contracts import (
    Knowledge,
    KnowledgeCandidate,
    KnowledgeScope,
    KnowledgeStatus,
    TruthCandidate,
)
from app.knowledge_engine.demoter import KnowledgeDemoter
from app.knowledge_engine.engine import KnowledgeEngine
from app.knowledge_engine.evaluator import KnowledgeCandidateEvaluator
from app.knowledge_engine.factory import TruthCandidateFactory
from app.knowledge_engine.graph import KnowledgeGraph
from app.knowledge_engine.memory import ScientificMemory
from app.knowledge_engine.promoter import KnowledgePromoter


def _make_orchestrator() -> tuple[CapabilityOrchestrator, KnowledgeEngine]:
    registry = CapabilityRegistry()
    orch = CapabilityOrchestrator(registry)
    engine = KnowledgeEngine()
    engine.register(orch)
    return orch, engine


def _make_candidate(confidence: float = 0.8, project: str = "test-project") -> KnowledgeCandidate:
    return KnowledgeCandidate(
        candidate_id=str(uuid.uuid4()),
        truth_candidate_id=str(uuid.uuid4()),
        title="Test Knowledge",
        proposition="Test proposition",
        domain="TEST",
        project=project,
        scope=KnowledgeScope.PROJECT,
        evidence=["evidence-001"],
        confidence=confidence,
        advisory_only=True,
    )


# ── Registration ───────────────────────────────────────────────────────────────

def test_capabilities_registered() -> None:
    orch, _ = _make_orchestrator()
    ids = orch.registered_ids()
    assert KnowledgeEngine.CAPABILITY_INGEST in ids
    assert KnowledgeEngine.CAPABILITY_QUERY in ids
    assert KnowledgeEngine.CAPABILITY_DEMOTE in ids
    assert KnowledgeEngine.CAPABILITY_STATS in ids


def test_capabilities_are_knowledge_kind() -> None:
    orch, _ = _make_orchestrator()
    caps = orch.discover(CapabilityKind.KNOWLEDGE)
    assert len(caps) == 4


# ── ScientificMemory (append-only) ────────────────────────────────────────────

def test_scientific_memory_appends() -> None:
    memory = ScientificMemory()
    memory.record("PROMOTED", "k-001", {"confidence": 0.9})
    memory.record("PROMOTED", "k-002", {"confidence": 0.7})
    assert memory.count() == 2


def test_scientific_memory_history() -> None:
    memory = ScientificMemory()
    memory.record("PROMOTED", "k-001", {"confidence": 0.9})
    memory.record("DEMOTED", "k-001", {"reason": "superseded"})
    history = memory.history("k-001")
    assert len(history) == 2


def test_scientific_memory_no_delete_method() -> None:
    memory = ScientificMemory()
    assert not hasattr(memory, "delete")
    assert not hasattr(memory, "update")
    assert not hasattr(memory, "remove")


def test_scientific_memory_all_events_are_immutable_list() -> None:
    memory = ScientificMemory()
    memory.record("X", "k-001", {})
    events = memory.all_events()
    # Modifying returned list should not affect internal state
    events.clear()
    assert memory.count() == 1


# ── Knowledge contract ────────────────────────────────────────────────────────

def test_knowledge_requires_evidence() -> None:
    with pytest.raises(AssertionError):
        Knowledge(
            knowledge_id="k-001",
            scientific_id="sci-001",
            lineage_id="lin-001",
            title="Test",
            proposition="Test",
            domain="TEST",
            project="test",
            scope=KnowledgeScope.PROJECT,
            evidence=[],  # must raise
            confidence=0.8,
        )


def test_knowledge_confidence_range() -> None:
    with pytest.raises(AssertionError):
        Knowledge(
            knowledge_id="k-001",
            scientific_id="sci-001",
            lineage_id="lin-001",
            title="Test",
            proposition="Test",
            domain="TEST",
            project="test",
            scope=KnowledgeScope.PROJECT,
            evidence=["e-001"],
            confidence=1.5,  # invalid
        )


# ── Evaluator ─────────────────────────────────────────────────────────────────

def test_evaluator_promotes_high_confidence() -> None:
    evaluator = KnowledgeCandidateEvaluator(threshold=0.6)
    candidate = _make_candidate(confidence=0.8)
    assert evaluator.should_promote(candidate) is True


def test_evaluator_rejects_low_confidence() -> None:
    evaluator = KnowledgeCandidateEvaluator(threshold=0.6)
    candidate = _make_candidate(confidence=0.4)
    assert evaluator.should_promote(candidate) is False


def test_evaluator_boundary_exactly_threshold() -> None:
    evaluator = KnowledgeCandidateEvaluator(threshold=0.6)
    candidate = _make_candidate(confidence=0.6)
    assert evaluator.should_promote(candidate) is True


# ── Promoter ──────────────────────────────────────────────────────────────────

def test_promoter_promotes_high_confidence() -> None:
    memory = ScientificMemory()
    graph = KnowledgeGraph()
    evaluator = KnowledgeCandidateEvaluator()
    promoter = KnowledgePromoter(evaluator, graph, memory)

    candidate = _make_candidate(confidence=0.9)
    knowledge = promoter.try_promote(candidate)
    assert knowledge is not None
    assert graph.count() == 1
    assert memory.count() == 1


def test_promoter_rejects_low_confidence() -> None:
    memory = ScientificMemory()
    graph = KnowledgeGraph()
    evaluator = KnowledgeCandidateEvaluator()
    promoter = KnowledgePromoter(evaluator, graph, memory)

    candidate = _make_candidate(confidence=0.3)
    knowledge = promoter.try_promote(candidate)
    assert knowledge is None
    assert graph.count() == 0
    assert memory.count() == 1  # REJECTED event recorded


# ── KnowledgeGraph ────────────────────────────────────────────────────────────

def test_graph_by_project() -> None:
    graph = KnowledgeGraph()
    k = Knowledge(
        knowledge_id="k-001", scientific_id="sci-001", lineage_id="lin-001",
        title="T", proposition="P", domain="D", project="crypto",
        scope=KnowledgeScope.PROJECT, evidence=["e-001"], confidence=0.8,
    )
    graph.add(k)
    assert len(graph.by_project("crypto")) == 1
    assert len(graph.by_project("other")) == 0


# ── Engine capabilities ────────────────────────────────────────────────────────

def test_ingest_promotes_healthy_observations() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=KnowledgeEngine.CAPABILITY_INGEST,
        inputs={
            "observations": [
                {"observation_id": "obs-001", "project": "poupi-crypto",
                 "domain": "CRYPTO", "health": "HEALTHY"},
                {"observation_id": "obs-002", "project": "poupi-crypto",
                 "domain": "CRYPTO", "health": "HEALTHY"},
            ]
        },
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert resp.outputs["advisory_only"] is True
    assert isinstance(resp.outputs["promoted"], list)
    assert isinstance(resp.outputs["rejected"], list)


def test_ingest_rejects_unknown_health() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=KnowledgeEngine.CAPABILITY_INGEST,
        inputs={
            "observations": [
                {"observation_id": "obs-001", "project": "test",
                 "domain": "TEST", "health": "UNKNOWN"},
            ]
        },
        context={},
    )
    resp = orch.execute(req)
    # UNKNOWN health → confidence=0.4 < 0.6 threshold → should be rejected
    assert len(resp.outputs["rejected"]) == 1
    assert len(resp.outputs["promoted"]) == 0


def test_stats_capability() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=KnowledgeEngine.CAPABILITY_STATS,
        inputs={},
        context={},
    )
    resp = orch.execute(req)
    assert "total_knowledge" in resp.outputs
    assert "total_events" in resp.outputs
    assert resp.outputs["advisory_only"] is True


def test_query_returns_empty_on_no_ingestion() -> None:
    orch, _ = _make_orchestrator()
    req = CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=KnowledgeEngine.CAPABILITY_QUERY,
        inputs={},
        context={},
    )
    resp = orch.execute(req)
    assert resp.advisory_only is True
    assert resp.outputs["count"] == 0


def test_engine_isolation() -> None:
    import app.knowledge_engine.engine as mod
    src = open(mod.__file__).read()
    for forbidden in ["intelligence_engine", "observation_engine", "development_engine",
                      "research_engine", "optimization_engine", "decision_engine"]:
        assert forbidden not in src
