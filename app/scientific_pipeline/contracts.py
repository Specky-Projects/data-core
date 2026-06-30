"""
TEAM B — Scientific Decision Pipeline
Universal pipeline contracts consumed by Mirror, Research and Business OS.
Implements only interfaces, DTOs, states, validations and dependency graph.
No decision logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


PIPELINE_CONTRACT_VERSION = "scientific-pipeline-v1"


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------


class PipelineStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"


class StageKind(str, Enum):
    CONTEXT = "CONTEXT"
    EVIDENCE = "EVIDENCE"
    BAYESIAN = "BAYESIAN"
    COMMITTEE = "COMMITTEE"
    EXPLAINABILITY = "EXPLAINABILITY"
    PREVIEW = "PREVIEW"
    LEARNING = "LEARNING"


class StageStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PipelineContext:
    """Immutable input bundle for one pipeline execution."""

    pipeline_id: str
    domain: str
    candidate_id: str
    lineage_id: str
    initiated_at: str
    initiator: str
    replay: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.pipeline_id:
            errors.append("pipeline_id is required")
        if not self.domain:
            errors.append("domain is required")
        if not self.candidate_id:
            errors.append("candidate_id is required")
        if not self.lineage_id:
            errors.append("lineage_id is required")
        return errors


# ---------------------------------------------------------------------------
# Stage contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageInput:
    stage: StageKind
    payload: dict[str, Any] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class StageOutput:
    stage: StageKind
    status: StageStatus
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float | None = None

    def passed(self) -> bool:
        return self.status == StageStatus.PASSED


@dataclass(frozen=True)
class StageContract:
    """Declares what a stage requires and produces."""

    kind: StageKind
    required_inputs: tuple[str, ...]
    produced_outputs: tuple[str, ...]
    depends_on: tuple[StageKind, ...] = ()
    optional: bool = False

    def validate_input(self, payload: dict[str, Any]) -> list[str]:
        missing = [k for k in self.required_inputs if k not in payload]
        return [f"{self.kind}.input missing: {k}" for k in missing]

    def validate_output(self, payload: dict[str, Any]) -> list[str]:
        missing = [k for k in self.produced_outputs if k not in payload]
        return [f"{self.kind}.output missing: {k}" for k in missing]


# ---------------------------------------------------------------------------
# Pipeline state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PipelineState:
    context: PipelineContext
    status: PipelineStatus
    current_stage: StageKind | None
    stage_outputs: dict[str, StageOutput] = field(default_factory=dict)
    errors: tuple[str, ...] = ()
    started_at: str | None = None
    finished_at: str | None = None

    def is_terminal(self) -> bool:
        return self.status in (
            PipelineStatus.COMPLETED,
            PipelineStatus.FAILED,
            PipelineStatus.BLOCKED,
        )

    def stage_passed(self, kind: StageKind) -> bool:
        output = self.stage_outputs.get(kind.value)
        return output is not None and output.passed()


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageTrace:
    stage: StageKind
    status: StageStatus
    input_hash: str | None
    output_hash: str | None
    duration_ms: float | None
    error: str | None = None


@dataclass(frozen=True)
class PipelineTrace:
    """Complete immutable record of one pipeline execution."""

    pipeline_id: str
    context: PipelineContext
    final_status: PipelineStatus
    stages: tuple[StageTrace, ...]
    total_duration_ms: float | None
    initiated_at: str
    finished_at: str | None

    def failed_stages(self) -> tuple[StageTrace, ...]:
        return tuple(s for s in self.stages if s.status == StageStatus.FAILED)

    def validate(self) -> list[str]:
        errors = list(self.context.validate())
        if not self.pipeline_id:
            errors.append("pipeline_id is required")
        if not self.initiated_at:
            errors.append("initiated_at is required")
        return errors


# ---------------------------------------------------------------------------
# Replay manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReplayInput:
    stage: StageKind
    payload_hash: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class PipelineReplayManifest:
    """Everything needed to deterministically re-execute a pipeline."""

    pipeline_id: str
    original_trace: PipelineTrace
    replay_inputs: tuple[ReplayInput, ...]
    contract_version: str = PIPELINE_CONTRACT_VERSION
    created_at: str | None = None

    def validate(self) -> list[str]:
        errors = list(self.original_trace.validate())
        if not self.replay_inputs:
            errors.append("replay_inputs must not be empty")
        return errors


# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------


STAGE_ORDER: tuple[StageKind, ...] = (
    StageKind.CONTEXT,
    StageKind.EVIDENCE,
    StageKind.BAYESIAN,
    StageKind.COMMITTEE,
    StageKind.EXPLAINABILITY,
    StageKind.PREVIEW,
    StageKind.LEARNING,
)

STAGE_CONTRACTS: dict[StageKind, StageContract] = {
    StageKind.CONTEXT: StageContract(
        kind=StageKind.CONTEXT,
        required_inputs=("candidate_id", "domain"),
        produced_outputs=("context_snapshot",),
    ),
    StageKind.EVIDENCE: StageContract(
        kind=StageKind.EVIDENCE,
        required_inputs=("context_snapshot",),
        produced_outputs=("evidence_bundle",),
        depends_on=(StageKind.CONTEXT,),
    ),
    StageKind.BAYESIAN: StageContract(
        kind=StageKind.BAYESIAN,
        required_inputs=("evidence_bundle",),
        produced_outputs=("posterior", "confidence"),
        depends_on=(StageKind.EVIDENCE,),
    ),
    StageKind.COMMITTEE: StageContract(
        kind=StageKind.COMMITTEE,
        required_inputs=("posterior", "confidence"),
        produced_outputs=("committee_verdict", "committee_confidence"),
        depends_on=(StageKind.BAYESIAN,),
    ),
    StageKind.EXPLAINABILITY: StageContract(
        kind=StageKind.EXPLAINABILITY,
        required_inputs=("committee_verdict", "posterior", "evidence_bundle"),
        produced_outputs=("explanation_tree",),
        depends_on=(StageKind.COMMITTEE,),
    ),
    StageKind.PREVIEW: StageContract(
        kind=StageKind.PREVIEW,
        required_inputs=("committee_verdict", "explanation_tree"),
        produced_outputs=("preview_record",),
        depends_on=(StageKind.EXPLAINABILITY,),
    ),
    StageKind.LEARNING: StageContract(
        kind=StageKind.LEARNING,
        required_inputs=("preview_record",),
        produced_outputs=("learning_signal",),
        depends_on=(StageKind.PREVIEW,),
        optional=True,
    ),
}


def dependency_graph() -> dict[StageKind, tuple[StageKind, ...]]:
    return {kind: contract.depends_on for kind, contract in STAGE_CONTRACTS.items()}


def execution_order() -> tuple[StageKind, ...]:
    return STAGE_ORDER


# ---------------------------------------------------------------------------
# Orchestrator interface
# ---------------------------------------------------------------------------


class ScientificDecisionPipeline:
    """
    Abstract orchestrator contract.
    Concrete implementations must not alter Mirror, Committee, Risk or Executor.
    """

    CONTRACT_VERSION = PIPELINE_CONTRACT_VERSION

    def run(self, context: PipelineContext) -> PipelineState:
        raise NotImplementedError

    def replay(self, manifest: PipelineReplayManifest) -> PipelineState:
        raise NotImplementedError

    def trace(self, pipeline_id: str) -> PipelineTrace | None:
        raise NotImplementedError
