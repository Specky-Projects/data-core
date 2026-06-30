from app.explainability_v2.contracts import (
    BayesianExplanation,
    CommitteeExplanation,
    CommitteeMemberExplanation,
    ContextExplanation,
    Counterfactual,
    CounterfactualDirection,
    CounterfactualSummary,
    DecisionTrace,
    EvidenceExplanation,
    ExplainabilityBuilder,
    ExplainabilityContract,
    ExplainabilityNode,
    ExplainabilityNodeKind,
    ExplainabilityRepository,
    ExplainabilityTree,
    HistoricalSimilarity,
)


def _bayesian() -> BayesianExplanation:
    return BayesianExplanation(prior=0.5, likelihood=0.7, posterior=0.65, evidence_weight=0.8)


def _committee() -> CommitteeExplanation:
    return CommitteeExplanation(
        verdict="APPROVE",
        confidence=0.75,
        quorum_met=True,
        members=(
            CommitteeMemberExplanation(member_id="m1", vote="APPROVE", weight=0.6),
            CommitteeMemberExplanation(member_id="m2", vote="APPROVE", weight=0.4),
        ),
    )


def _context() -> ContextExplanation:
    return ContextExplanation(domain="crypto", candidate_id="c1", regime="BULL", strategy="specky", captured_at="t")


def _evidence_used() -> EvidenceExplanation:
    return EvidenceExplanation(
        evidence_id="ev-001",
        source_type="mirror",
        source_name="mirror-trade",
        evidence_level="OBSERVED",
        quality_score=0.8,
        contribution_weight=0.6,
        used=True,
    )


def _counterfactuals(decision_id: str = "d1") -> CounterfactualSummary:
    cf = Counterfactual(
        counterfactual_id="cf-001",
        description="if confidence were 0.3",
        changed_feature="confidence",
        original_value=0.8,
        counterfactual_value=0.3,
        direction=CounterfactualDirection.WOULD_REJECT,
        confidence_delta=-0.5,
    )
    return CounterfactualSummary(
        decision_id=decision_id,
        counterfactuals=(cf,),
        most_influential_change="confidence",
        would_change_decision=True,
    )


def _trace(decision_id: str = "d1") -> DecisionTrace:
    return DecisionTrace(
        trace_id="trace-001",
        decision_id=decision_id,
        lineage_id="lin-001",
        domain="crypto",
        context=_context(),
        evidence_used=(_evidence_used(),),
        evidence_absent=(),
        bayesian=_bayesian(),
        committee=_committee(),
        confidence=0.75,
        risk=0.2,
        expected_edge=0.04,
        historical_similarities=(),
        counterfactuals=_counterfactuals(decision_id),
        final_decision="APPROVE",
        final_action="EXECUTE",
        traced_at="2026-06-30T00:00:00Z",
    )


def _tree(decision_id: str = "d1") -> ExplainabilityTree:
    root = ExplainabilityNode(
        node_id="n1",
        kind=ExplainabilityNodeKind.FINAL_DECISION,
        label="APPROVE",
        value="APPROVE",
        weight=1.0,
    )
    return ExplainabilityTree(
        tree_id="tree-001",
        decision_id=decision_id,
        root=root,
        total_nodes=1,
        max_depth=1,
        built_at="2026-06-30T00:00:00Z",
    )


def test_bayesian_validates() -> None:
    assert _bayesian().validate() == []


def test_bayesian_invalid_value() -> None:
    b = BayesianExplanation(prior=1.5, likelihood=0.5, posterior=0.6, evidence_weight=0.7)
    errors = b.validate()
    assert any("prior" in e for e in errors)


def test_evidence_explanation_validates() -> None:
    assert _evidence_used().validate() == []


def test_evidence_invalid_contribution_weight() -> None:
    ev = EvidenceExplanation(
        evidence_id="ev-001",
        source_type="x",
        source_name="y",
        evidence_level="OBSERVED",
        quality_score=0.5,
        contribution_weight=2.0,
    )
    errors = ev.validate()
    assert any("contribution_weight" in e for e in errors)


def test_counterfactual_validates() -> None:
    assert _counterfactuals().validate() == []


def test_historical_similarity_validates() -> None:
    sim = HistoricalSimilarity(similar_case_id="c1", similarity_score=0.9, outcome="WIN", domain="crypto", captured_at="t")
    assert sim.validate() == []


def test_historical_similarity_invalid_score() -> None:
    sim = HistoricalSimilarity(similar_case_id="c1", similarity_score=1.5, outcome=None, domain="crypto", captured_at="t")
    assert sim.validate() != []


def test_decision_trace_validates() -> None:
    assert _trace().validate() == []


def test_decision_trace_invalid_confidence() -> None:
    t = DecisionTrace(
        trace_id="t1",
        decision_id="d1",
        lineage_id="l1",
        domain="crypto",
        context=_context(),
        evidence_used=(),
        evidence_absent=(),
        bayesian=_bayesian(),
        committee=_committee(),
        confidence=2.0,
        risk=None,
        expected_edge=None,
        historical_similarities=(),
        counterfactuals=_counterfactuals(),
        final_decision="APPROVE",
        final_action="EXECUTE",
        traced_at="t",
    )
    errors = t.validate()
    assert any("confidence" in e for e in errors)


def test_explainability_tree_validates() -> None:
    assert _tree().validate() == []


def test_tree_node_all_nodes() -> None:
    child = ExplainabilityNode(node_id="n2", kind=ExplainabilityNodeKind.EVIDENCE_USED, label="ev", value="ev-001")
    root = ExplainabilityNode(node_id="n1", kind=ExplainabilityNodeKind.FINAL_DECISION, label="APPROVE", value="APPROVE", children=(child,))
    assert len(root.all_nodes()) == 2


def test_explainability_contract_validates() -> None:
    contract = ExplainabilityContract(
        contract_id="ec-001",
        decision_id="d1",
        lineage_id="lin-001",
        trace=_trace(),
        tree=_tree(),
        counterfactuals=_counterfactuals(),
        generated_at="2026-06-30T00:00:00Z",
    )
    assert contract.validate() == []


def test_explainability_contract_missing_id() -> None:
    contract = ExplainabilityContract(
        contract_id="",
        decision_id="d1",
        lineage_id="lin-001",
        trace=_trace(),
        tree=_tree(),
        counterfactuals=_counterfactuals(),
        generated_at="t",
    )
    errors = contract.validate()
    assert any("contract_id" in e for e in errors)


def test_repository_is_abstract() -> None:
    repo = ExplainabilityRepository()
    try:
        repo.load("d1")
        assert False
    except NotImplementedError:
        pass


def test_builder_is_advisory_only() -> None:
    builder = ExplainabilityBuilder()
    assert builder.ADVISORY_ONLY is True
