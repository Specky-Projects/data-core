"""Explainability binding — projects a consumer decision onto the canonical
ExplainabilityContract (DecisionTrace + ExplainabilityTree + Counterfactuals).

Read-only: it explains a decision that already happened; it never re-scores it.
"""
from __future__ import annotations

from app.explainability_v2.contracts import (
    BayesianExplanation,
    CommitteeExplanation,
    CommitteeMemberExplanation,
    ContextExplanation,
    CounterfactualSummary,
    DecisionTrace,
    EvidenceExplanation,
    ExplainabilityContract,
    ExplainabilityNode,
    ExplainabilityNodeKind,
    ExplainabilityTree,
)
from app.scientific_consumers.facts import DecisionFacts
from app.scientific_identity.contract import stable_hash


def _context(facts: DecisionFacts) -> ContextExplanation:
    return ContextExplanation(
        domain=facts.domain, candidate_id=facts.candidate_id,
        regime=facts.regime, strategy=facts.strategy, captured_at=facts.decided_at,
    )


def _evidence(facts: DecisionFacts) -> tuple[tuple[EvidenceExplanation, ...], tuple[EvidenceExplanation, ...]]:
    used, absent = [], []
    for e in facts.evidence:
        ex = EvidenceExplanation(
            evidence_id=e.evidence_id, source_type=e.source_type, source_name=e.source_name,
            evidence_level=e.evidence_level, quality_score=e.quality_score,
            contribution_weight=e.contribution_weight, used=e.used,
            reason_absent=None if e.used else "not_used_by_consumer",
        )
        (used if e.used else absent).append(ex)
    return tuple(used), tuple(absent)


def _committee(facts: DecisionFacts) -> CommitteeExplanation:
    return CommitteeExplanation(
        verdict=facts.committee_verdict, confidence=facts.committee_confidence,
        quorum_met=facts.committee_quorum_met,
        members=tuple(
            CommitteeMemberExplanation(m.member_id, m.vote, m.weight, m.rationale)
            for m in facts.committee_members
        ),
        dissenting_votes=facts.committee_dissenting,
    )


def build_decision_trace(facts: DecisionFacts) -> DecisionTrace:
    used, absent = _evidence(facts)
    return DecisionTrace(
        trace_id=stable_hash({"lineage": facts.lineage_id, "kind": "decision_trace"}),
        decision_id=facts.decision_id, lineage_id=facts.lineage_id, domain=facts.domain,
        context=_context(facts), evidence_used=used, evidence_absent=absent,
        bayesian=BayesianExplanation(
            prior=facts.prior, likelihood=facts.likelihood,
            posterior=facts.posterior, evidence_weight=facts.evidence_weight,
        ),
        committee=_committee(facts), confidence=facts.confidence,
        risk=facts.risk, expected_edge=facts.expected_edge,
        historical_similarities=(),
        counterfactuals=CounterfactualSummary(
            decision_id=facts.decision_id, counterfactuals=(),
            most_influential_change=None, would_change_decision=False,
        ),
        final_decision=facts.verdict, final_action=facts.action, traced_at=facts.decided_at,
    )


def build_tree(facts: DecisionFacts) -> ExplainabilityTree:
    children = (
        ExplainabilityNode(node_id=stable_hash({"n": "ctx", "l": facts.lineage_id}),
                           kind=ExplainabilityNodeKind.CONTEXT, label="context",
                           value={"regime": facts.regime, "strategy": facts.strategy}),
        ExplainabilityNode(node_id=stable_hash({"n": "bay", "l": facts.lineage_id}),
                           kind=ExplainabilityNodeKind.BAYESIAN, label="posterior",
                           value=facts.posterior, weight=facts.evidence_weight),
        ExplainabilityNode(node_id=stable_hash({"n": "com", "l": facts.lineage_id}),
                           kind=ExplainabilityNodeKind.COMMITTEE, label="committee",
                           value=facts.committee_verdict, weight=facts.committee_confidence),
    )
    root = ExplainabilityNode(
        node_id=stable_hash({"n": "root", "l": facts.lineage_id}),
        kind=ExplainabilityNodeKind.FINAL_DECISION, label=facts.verdict,
        value={"action": facts.action, "confidence": facts.confidence}, children=children,
    )
    all_nodes = root.all_nodes()
    return ExplainabilityTree(
        tree_id=stable_hash({"lineage": facts.lineage_id, "kind": "tree"}),
        decision_id=facts.decision_id, root=root,
        total_nodes=len(all_nodes), max_depth=2, built_at=facts.decided_at,
    )


def build_explainability(facts: DecisionFacts) -> ExplainabilityContract:
    trace = build_decision_trace(facts)
    return ExplainabilityContract(
        contract_id=stable_hash({"lineage": facts.lineage_id, "kind": "explainability"}),
        decision_id=facts.decision_id, lineage_id=facts.lineage_id,
        trace=trace, tree=build_tree(facts), counterfactuals=trace.counterfactuals,
        generated_at=facts.decided_at,
    )
