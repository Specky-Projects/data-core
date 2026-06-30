"""
TEAM E — Explainability V2
Every decision becomes fully explainable.
Contracts only — must not alter any decision logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


EXPLAINABILITY_CONTRACT_VERSION = "explainability-v2"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ExplainabilityNodeKind(StrEnum):
    CONTEXT = "CONTEXT"
    EVIDENCE_USED = "EVIDENCE_USED"
    EVIDENCE_ABSENT = "EVIDENCE_ABSENT"
    BAYESIAN = "BAYESIAN"
    COMMITTEE = "COMMITTEE"
    CONFIDENCE = "CONFIDENCE"
    RISK = "RISK"
    EDGE = "EDGE"
    SIMILARITY = "SIMILARITY"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    FINAL_DECISION = "FINAL_DECISION"


class CounterfactualDirection(StrEnum):
    WOULD_APPROVE = "WOULD_APPROVE"
    WOULD_REJECT = "WOULD_REJECT"
    WOULD_DELAY = "WOULD_DELAY"
    UNCHANGED = "UNCHANGED"


# ---------------------------------------------------------------------------
# Context explanation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContextExplanation:
    domain: str
    candidate_id: str
    regime: str | None
    strategy: str | None
    captured_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Evidence explanation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceExplanation:
    evidence_id: str
    source_type: str
    source_name: str
    evidence_level: str
    quality_score: float | None
    contribution_weight: float | None
    used: bool = True
    reason_absent: str | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.evidence_id:
            errors.append("evidence_id is required")
        if self.contribution_weight is not None and not 0.0 <= self.contribution_weight <= 1.0:
            errors.append("contribution_weight must be between 0 and 1")
        return errors


# ---------------------------------------------------------------------------
# Bayesian explanation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BayesianExplanation:
    prior: float
    likelihood: float
    posterior: float
    evidence_weight: float
    feature_contributions: dict[str, float] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        for field_name, value in [
            ("prior", self.prior),
            ("likelihood", self.likelihood),
            ("posterior", self.posterior),
            ("evidence_weight", self.evidence_weight),
        ]:
            if not 0.0 <= value <= 1.0:
                errors.append(f"{field_name} must be between 0 and 1")
        return errors


# ---------------------------------------------------------------------------
# Committee explanation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommitteeMemberExplanation:
    member_id: str
    vote: str
    weight: float
    rationale: str | None = None


@dataclass(frozen=True)
class CommitteeExplanation:
    verdict: str
    confidence: float
    quorum_met: bool
    members: tuple[CommitteeMemberExplanation, ...]
    dissenting_votes: int = 0


# ---------------------------------------------------------------------------
# Historical similarity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HistoricalSimilarity:
    similar_case_id: str
    similarity_score: float
    outcome: str | None
    domain: str
    captured_at: str

    def validate(self) -> list[str]:
        if not 0.0 <= self.similarity_score <= 1.0:
            return ["similarity_score must be between 0 and 1"]
        return []


# ---------------------------------------------------------------------------
# Counterfactual
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Counterfactual:
    counterfactual_id: str
    description: str
    changed_feature: str
    original_value: Any
    counterfactual_value: Any
    direction: CounterfactualDirection
    confidence_delta: float | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.counterfactual_id:
            errors.append("counterfactual_id is required")
        if not self.changed_feature:
            errors.append("changed_feature is required")
        return errors


@dataclass(frozen=True)
class CounterfactualSummary:
    decision_id: str
    counterfactuals: tuple[Counterfactual, ...]
    most_influential_change: str | None
    would_change_decision: bool

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.decision_id:
            errors.append("decision_id is required")
        for cf in self.counterfactuals:
            errors.extend(cf.validate())
        return errors


# ---------------------------------------------------------------------------
# Decision trace
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionTrace:
    """Complete causal trace of a single decision."""

    trace_id: str
    decision_id: str
    lineage_id: str
    domain: str
    context: ContextExplanation
    evidence_used: tuple[EvidenceExplanation, ...]
    evidence_absent: tuple[EvidenceExplanation, ...]
    bayesian: BayesianExplanation
    committee: CommitteeExplanation
    confidence: float
    risk: float | None
    expected_edge: float | None
    historical_similarities: tuple[HistoricalSimilarity, ...]
    counterfactuals: CounterfactualSummary
    final_decision: str
    final_action: str
    traced_at: str
    contract_version: str = EXPLAINABILITY_CONTRACT_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.trace_id:
            errors.append("trace_id is required")
        if not self.decision_id:
            errors.append("decision_id is required")
        if not 0.0 <= self.confidence <= 1.0:
            errors.append("confidence must be between 0 and 1")
        if self.risk is not None and not 0.0 <= self.risk <= 1.0:
            errors.append("risk must be between 0 and 1")
        errors.extend(self.bayesian.validate())
        errors.extend(self.counterfactuals.validate())
        for ev in self.evidence_used + self.evidence_absent:
            errors.extend(ev.validate())
        return errors


# ---------------------------------------------------------------------------
# Explainability tree
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExplainabilityNode:
    node_id: str
    kind: ExplainabilityNodeKind
    label: str
    value: Any
    weight: float | None = None
    children: tuple["ExplainabilityNode", ...] = ()

    def all_nodes(self) -> list["ExplainabilityNode"]:
        nodes = [self]
        for child in self.children:
            nodes.extend(child.all_nodes())
        return nodes


@dataclass(frozen=True)
class ExplainabilityTree:
    tree_id: str
    decision_id: str
    root: ExplainabilityNode
    total_nodes: int
    max_depth: int
    built_at: str

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.tree_id:
            errors.append("tree_id is required")
        if not self.decision_id:
            errors.append("decision_id is required")
        return errors


# ---------------------------------------------------------------------------
# Contract interface
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExplainabilityContract:
    """Top-level explainability contract for one decision."""

    contract_id: str
    decision_id: str
    lineage_id: str
    trace: DecisionTrace
    tree: ExplainabilityTree
    counterfactuals: CounterfactualSummary
    generated_at: str
    contract_version: str = EXPLAINABILITY_CONTRACT_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.contract_id:
            errors.append("contract_id is required")
        errors.extend(self.trace.validate())
        errors.extend(self.tree.validate())
        errors.extend(self.counterfactuals.validate())
        return errors


# ---------------------------------------------------------------------------
# Repository interface
# ---------------------------------------------------------------------------


class ExplainabilityRepository:
    """Abstract write-once explainability store."""

    def save(self, contract: ExplainabilityContract) -> None:
        raise NotImplementedError

    def load(self, decision_id: str) -> ExplainabilityContract | None:
        raise NotImplementedError

    def load_trace(self, decision_id: str) -> DecisionTrace | None:
        raise NotImplementedError

    def load_tree(self, decision_id: str) -> ExplainabilityTree | None:
        raise NotImplementedError

    def load_counterfactuals(self, decision_id: str) -> CounterfactualSummary | None:
        raise NotImplementedError


class ExplainabilityBuilder:
    """Abstract builder — implementations must not alter decisions."""

    ADVISORY_ONLY: bool = True

    def build(self, decision_id: str, context: dict[str, Any]) -> ExplainabilityContract:
        raise NotImplementedError

    def build_tree(self, trace: DecisionTrace) -> ExplainabilityTree:
        raise NotImplementedError

    def build_counterfactuals(self, trace: DecisionTrace) -> CounterfactualSummary:
        raise NotImplementedError
