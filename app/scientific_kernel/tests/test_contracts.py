from app.scientific_kernel.contracts import (
    ArchitectureFitnessReport,
    ArchitectureFitnessRule,
    ClaimStatus,
    ConfidenceScore,
    ConfidenceSource,
    CounterfactualInput,
    CounterfactualResult,
    EvidenceKind,
    EvidenceQuality,
    Experiment,
    ExperimentHypothesis,
    ExperimentStatus,
    FitnessResult,
    KnowledgeEdge,
    KnowledgeEdgeKind,
    KnowledgeGraph,
    KnowledgeNode,
    ReplayInput,
    ReplayResult,
    ReplayStatus,
    ScientificClaim,
    ScientificEvidence,
    ScientificIdentity,
    ScientificKernelAdapter,
    ScientificMemory,
    ScientificMemoryEntry,
)


def test_evidence_validates() -> None:
    ev = ScientificEvidence(
        evidence_id="ev-001",
        kind=EvidenceKind.EMPIRICAL,
        source_module="app.mirror.trade",
        captured_at="2026-06-30T00:00:00Z",
        quality=EvidenceQuality.HIGH,
        payload_hash="abc123",
        confidence=0.8,
    )
    assert ev.validate() == []


def test_evidence_invalid_confidence() -> None:
    ev = ScientificEvidence(
        evidence_id="ev-001",
        kind=EvidenceKind.SIMULATED,
        source_module="app.research",
        captured_at="t",
        quality=EvidenceQuality.LOW,
        payload_hash="x",
        confidence=1.5,
    )
    assert ev.validate() != []


def test_claim_validates() -> None:
    claim = ScientificClaim(
        claim_id="cl-001",
        domain="crypto",
        statement="B2B_FADE has positive edge",
        status=ClaimStatus.SUPPORTED,
        evidence_refs=("ev-001",),
        confidence=0.85,
        created_at="2026-06-30T00:00:00Z",
    )
    assert claim.validate() == []


def test_claim_requires_evidence_refs() -> None:
    claim = ScientificClaim(
        claim_id="cl-001",
        domain="crypto",
        statement="unsupported claim",
        status=ClaimStatus.PROPOSED,
        evidence_refs=(),
        confidence=0.5,
        created_at="t",
    )
    errors = claim.validate()
    assert any("evidence" in e for e in errors)


def test_replay_result_diverged_requires_reason() -> None:
    result = ReplayResult(
        replay_id="r1",
        original_decision_id="d1",
        status=ReplayStatus.DIVERGED,
        replayed_action="REJECT",
        original_action="APPROVE",
        deterministic=False,
    )
    errors = result.validate()
    assert any("divergence_reason" in e for e in errors)


def test_replay_result_completed_validates() -> None:
    result = ReplayResult(
        replay_id="r1",
        original_decision_id="d1",
        status=ReplayStatus.COMPLETED,
        replayed_action="APPROVE",
        original_action="APPROVE",
        deterministic=True,
    )
    assert result.validate() == []


def test_counterfactual_input_validates() -> None:
    inp = CounterfactualInput(
        counterfactual_id="cf-001",
        decision_id="d1",
        feature_overrides={"confidence": 0.3},
        narrative="what if confidence were lower",
    )
    assert inp.validate() == []


def test_counterfactual_input_empty_overrides_invalid() -> None:
    inp = CounterfactualInput(
        counterfactual_id="cf-001",
        decision_id="d1",
        feature_overrides={},
        narrative="nothing changed",
    )
    errors = inp.validate()
    assert any("feature_overrides" in e for e in errors)


def test_knowledge_graph_validates() -> None:
    n1 = KnowledgeNode(node_id="n1", domain="crypto", label="regime", kind="CONTEXT", confidence=0.9)
    n2 = KnowledgeNode(node_id="n2", domain="crypto", label="edge", kind="OUTCOME", confidence=0.7)
    edge = KnowledgeEdge(edge_id="e1", source_node_id="n1", target_node_id="n2", kind=KnowledgeEdgeKind.CAUSES, weight=0.8)
    graph = KnowledgeGraph(graph_id="g1", domain="crypto", nodes=(n1, n2), edges=(edge,), built_at="t")
    assert graph.validate() == []
    assert graph.neighbors("n1") == (n2,)


def test_knowledge_graph_invalid_edge() -> None:
    n1 = KnowledgeNode(node_id="n1", domain="crypto", label="x", kind="y", confidence=0.5)
    edge = KnowledgeEdge(edge_id="e1", source_node_id="n1", target_node_id="n999", kind=KnowledgeEdgeKind.CORRELATES, weight=0.5)
    graph = KnowledgeGraph(graph_id="g1", domain="crypto", nodes=(n1,), edges=(edge,), built_at="t")
    errors = graph.validate()
    assert any("target_node_id" in e for e in errors)


def test_scientific_memory_find() -> None:
    entry = ScientificMemoryEntry(
        entry_id="e1", domain="crypto", scope="GLOBAL", key="regime", value_hash="abc", recorded_at="t"
    )
    mem = ScientificMemory(memory_id="m1", domain="crypto", scope="GLOBAL", entries=(entry,))
    assert mem.find("regime") == entry
    assert mem.find("missing") is None


def test_confidence_score_validates() -> None:
    cs = ConfidenceScore(score=0.75, source=ConfidenceSource.ENSEMBLE)
    assert cs.validate() == []


def test_confidence_score_out_of_range() -> None:
    cs = ConfidenceScore(score=1.5, source=ConfidenceSource.BAYESIAN)
    assert cs.validate() != []


def test_scientific_identity_validates() -> None:
    identity = ScientificIdentity(
        identity_id="id-001",
        domain="crypto",
        kind="decision",
        fingerprint="abc123",
        created_at="t",
        version="v1",
    )
    assert identity.validate() == []


def test_fitness_report_failed_rules() -> None:
    r1 = ArchitectureFitnessRule(rule_id="r1", description="no direct deps", result=FitnessResult.PASS, violations=(), checked_at="t")
    r2 = ArchitectureFitnessRule(rule_id="r2", description="contracts only", result=FitnessResult.FAIL, violations=("legacy import found",), checked_at="t")
    report = ArchitectureFitnessReport(report_id="rep-001", domain="crypto", rules=(r1, r2), overall=FitnessResult.FAIL, generated_at="t")
    failed = report.failed_rules()
    assert len(failed) == 1
    assert failed[0].rule_id == "r2"


def test_experiment_validates() -> None:
    exp = Experiment(
        experiment_id="exp-001",
        domain="crypto",
        hypothesis=ExperimentHypothesis(hypothesis_id="h1", statement="B2B_FADE ROI > 0"),
        status=ExperimentStatus.RUNNING,
        started_at="2026-06-30T00:00:00Z",
        completed_at=None,
    )
    assert exp.validate() == []


def test_kernel_adapter_is_abstract() -> None:
    adapter = ScientificKernelAdapter()
    try:
        adapter.resolve_evidence("app.mirror", "ev-001")
        assert False
    except NotImplementedError:
        pass
