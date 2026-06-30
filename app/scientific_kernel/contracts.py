"""
TEAM F — Scientific Kernel Contracts
Consolidated reusable scientific contracts for the entire platform.
All implementations must be provided via adapters referencing existing modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


KERNEL_CONTRACTS_VERSION = "scientific-kernel-contracts-v1"


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


class EvidenceKind(StrEnum):
    EMPIRICAL = "EMPIRICAL"
    STATISTICAL = "STATISTICAL"
    CAUSAL = "CAUSAL"
    THEORETICAL = "THEORETICAL"
    REPLAY = "REPLAY"
    SIMULATED = "SIMULATED"
    EXCHANGE = "EXCHANGE"


class EvidenceQuality(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ScientificEvidence:
    evidence_id: str
    kind: EvidenceKind
    source_module: str
    captured_at: str
    quality: EvidenceQuality
    payload_hash: str
    sample_size: int | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.evidence_id:
            errors.append("evidence_id is required")
        if not self.source_module:
            errors.append("source_module is required")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            errors.append("confidence must be between 0 and 1")
        return errors


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------


class ClaimStatus(StrEnum):
    PROPOSED = "PROPOSED"
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    DEPRECATED = "DEPRECATED"


@dataclass(frozen=True)
class ScientificClaim:
    claim_id: str
    domain: str
    statement: str
    status: ClaimStatus
    evidence_refs: tuple[str, ...]
    confidence: float
    created_at: str
    updated_at: str | None = None
    refutation_reason: str | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.claim_id:
            errors.append("claim_id is required")
        if not self.statement:
            errors.append("statement is required")
        if not 0.0 <= self.confidence <= 1.0:
            errors.append("confidence must be between 0 and 1")
        if not self.evidence_refs:
            errors.append("claims must reference at least one evidence")
        return errors


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


class ReplayStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    DIVERGED = "DIVERGED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ReplayInput:
    replay_id: str
    original_decision_id: str
    input_snapshot_hash: str
    initiated_at: str
    initiator: str


@dataclass(frozen=True)
class ReplayResult:
    replay_id: str
    original_decision_id: str
    status: ReplayStatus
    replayed_action: str | None
    original_action: str
    deterministic: bool
    divergence_reason: str | None = None
    completed_at: str | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.replay_id:
            errors.append("replay_id is required")
        if not self.original_decision_id:
            errors.append("original_decision_id is required")
        if self.status == ReplayStatus.DIVERGED and not self.divergence_reason:
            errors.append("diverged replay must include divergence_reason")
        return errors


# ---------------------------------------------------------------------------
# Counterfactual
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CounterfactualInput:
    counterfactual_id: str
    decision_id: str
    feature_overrides: dict[str, Any]
    narrative: str

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.counterfactual_id:
            errors.append("counterfactual_id is required")
        if not self.decision_id:
            errors.append("decision_id is required")
        if not self.feature_overrides:
            errors.append("feature_overrides must not be empty")
        return errors


@dataclass(frozen=True)
class CounterfactualResult:
    counterfactual_id: str
    decision_id: str
    original_action: str
    counterfactual_action: str
    changed: bool
    confidence_delta: float | None = None


# ---------------------------------------------------------------------------
# Knowledge Graph
# ---------------------------------------------------------------------------


class KnowledgeEdgeKind(StrEnum):
    CAUSES = "CAUSES"
    CORRELATES = "CORRELATES"
    CONTRADICTS = "CONTRADICTS"
    SUPPORTS = "SUPPORTS"
    DERIVES_FROM = "DERIVES_FROM"


@dataclass(frozen=True)
class KnowledgeNode:
    node_id: str
    domain: str
    label: str
    kind: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    kind: KnowledgeEdgeKind
    weight: float
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class KnowledgeGraph:
    graph_id: str
    domain: str
    nodes: tuple[KnowledgeNode, ...]
    edges: tuple[KnowledgeEdge, ...]
    built_at: str

    def neighbors(self, node_id: str) -> tuple[KnowledgeNode, ...]:
        connected_ids = {e.target_node_id for e in self.edges if e.source_node_id == node_id}
        return tuple(n for n in self.nodes if n.node_id in connected_ids)

    def validate(self) -> list[str]:
        errors: list[str] = []
        node_ids = {n.node_id for n in self.nodes}
        for edge in self.edges:
            if edge.source_node_id not in node_ids:
                errors.append(f"edge {edge.edge_id}: source_node_id not found")
            if edge.target_node_id not in node_ids:
                errors.append(f"edge {edge.edge_id}: target_node_id not found")
        return errors


# ---------------------------------------------------------------------------
# Scientific Memory
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScientificMemoryEntry:
    entry_id: str
    domain: str
    scope: str
    key: str
    value_hash: str
    recorded_at: str
    expires_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScientificMemory:
    memory_id: str
    domain: str
    scope: str
    entries: tuple[ScientificMemoryEntry, ...]

    def find(self, key: str) -> ScientificMemoryEntry | None:
        return next((e for e in self.entries if e.key == key), None)


# ---------------------------------------------------------------------------
# Execution Memory
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionMemoryRecord:
    record_id: str
    lineage_id: str
    decision_id: str
    action: str
    domain: str
    strategy: str | None
    recorded_at: str
    outcome_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.record_id:
            errors.append("record_id is required")
        if not self.lineage_id:
            errors.append("lineage_id is required")
        if not self.decision_id:
            errors.append("decision_id is required")
        return errors


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


class ConfidenceSource(StrEnum):
    BAYESIAN = "BAYESIAN"
    COMMITTEE = "COMMITTEE"
    HISTORICAL = "HISTORICAL"
    ENSEMBLE = "ENSEMBLE"
    CALIBRATED = "CALIBRATED"


@dataclass(frozen=True)
class ConfidenceScore:
    score: float
    source: ConfidenceSource
    sample_size: int | None = None
    calibration_delta: float | None = None
    valid: bool = True

    def validate(self) -> list[str]:
        if not 0.0 <= self.score <= 1.0:
            return ["confidence score must be between 0 and 1"]
        return []


# ---------------------------------------------------------------------------
# Semantic Projection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SemanticProjection:
    projection_id: str
    source_id: str
    domain: str
    embedding_ref: str
    projected_at: str
    dimensions: int
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Scientific Identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScientificIdentity:
    """Stable identity of a scientific artifact across versions."""

    identity_id: str
    domain: str
    kind: str
    fingerprint: str
    created_at: str
    version: str

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.identity_id:
            errors.append("identity_id is required")
        if not self.fingerprint:
            errors.append("fingerprint is required")
        return errors


# ---------------------------------------------------------------------------
# Architecture Fitness
# ---------------------------------------------------------------------------


class FitnessResult(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ArchitectureFitnessRule:
    rule_id: str
    description: str
    result: FitnessResult
    violations: tuple[str, ...]
    checked_at: str


@dataclass(frozen=True)
class ArchitectureFitnessReport:
    report_id: str
    domain: str
    rules: tuple[ArchitectureFitnessRule, ...]
    overall: FitnessResult
    generated_at: str

    def failed_rules(self) -> tuple[ArchitectureFitnessRule, ...]:
        return tuple(r for r in self.rules if r.result == FitnessResult.FAIL)

    def validate(self) -> list[str]:
        if not self.report_id:
            return ["report_id is required"]
        return []


# ---------------------------------------------------------------------------
# Experiment
# ---------------------------------------------------------------------------


class ExperimentStatus(StrEnum):
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


@dataclass(frozen=True)
class ExperimentHypothesis:
    hypothesis_id: str
    statement: str
    claim_ref: str | None = None


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    domain: str
    hypothesis: ExperimentHypothesis
    status: ExperimentStatus
    started_at: str | None
    completed_at: str | None
    evidence_refs: tuple[str, ...] = ()
    outcome_claim_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.experiment_id:
            errors.append("experiment_id is required")
        if not self.hypothesis.statement:
            errors.append("hypothesis.statement is required")
        return errors


# ---------------------------------------------------------------------------
# Kernel adapter interface
# ---------------------------------------------------------------------------


class ScientificKernelAdapter:
    """
    Adapts existing implementations to kernel contracts.
    Implementations must reuse existing modules — never re-implement.
    """

    CONTRACT_VERSION: str = KERNEL_CONTRACTS_VERSION

    def resolve_evidence(self, source_module: str, ref_id: str) -> ScientificEvidence | None:
        raise NotImplementedError

    def resolve_claim(self, claim_id: str) -> ScientificClaim | None:
        raise NotImplementedError

    def resolve_replay(self, replay_id: str) -> ReplayResult | None:
        raise NotImplementedError

    def resolve_knowledge_graph(self, domain: str) -> KnowledgeGraph | None:
        raise NotImplementedError

    def resolve_memory(self, domain: str, scope: str) -> ScientificMemory | None:
        raise NotImplementedError

    def resolve_confidence(self, decision_id: str) -> ConfidenceScore | None:
        raise NotImplementedError

    def resolve_identity(self, artifact_id: str) -> ScientificIdentity | None:
        raise NotImplementedError
