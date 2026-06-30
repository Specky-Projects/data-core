"""Business OS 5.0 — Universal Execution Log canonical contracts.

The UEL is the flight-recorder of the Business OS ecosystem. Every execution
from every project (Crypto, Baby, Sinalo, future) is represented by a single
canonical contract — preserving full traceability, lineage, evidence, learning,
and replay-safety without replacing any project-specific log.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

UEL_VERSION = "business-os-5.0-universal-execution-log"
UEL_SCHEMA_VERSION = "uel-v1-5.0"


# ── Enums ──────────────────────────────────────────────────────────────────────


class ExecutionSurface(StrEnum):
    TRADING = "trading"
    SEO = "seo"
    CONTENT = "content"
    AFFILIATE = "affiliate"
    SOCIAL_MEDIA = "social_media"
    ANALYTICS = "analytics"
    RESEARCH = "research"
    REPLAY = "replay"
    EXPERIMENT = "experiment"
    SIMULATION = "simulation"
    MANUAL_ACTION = "manual_action"
    API_CALL = "api_call"
    SCHEDULER = "scheduler"
    HUMAN_REVIEW = "human_review"
    AUTONOMOUS_DECISION = "autonomous_decision"
    WORKFLOW = "workflow"
    EXTERNAL_CONNECTOR = "external_connector"
    UNKNOWN = "unknown"


class ExecutionType(StrEnum):
    """Functional classification of what the execution *does*."""
    TRADE = "trade"
    SIGNAL = "signal"
    DISCOVERY = "discovery"
    SCRAPE = "scrape"
    COLLECT = "collect"
    ANALYZE = "analyze"
    SCORE = "score"
    RANK = "rank"
    ALERT = "alert"
    PUBLISH = "publish"
    REVIEW = "review"
    APPROVE = "approve"
    ROLLBACK = "rollback"
    REPLAY = "replay"
    EXPERIMENT = "experiment"
    SIMULATE = "simulate"
    TRAIN = "train"
    INFER = "infer"
    REPORT = "report"
    NOTIFY = "notify"
    SCHEDULE = "schedule"
    ORCHESTRATE = "orchestrate"
    UNKNOWN = "unknown"


class UELStatus(StrEnum):
    PLANNED = "planned"
    APPROVED = "approved"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLBACK = "rollback"
    CANCELLED = "cancelled"
    PARTIAL = "partial"
    SHADOW = "shadow"
    SIMULATION = "simulation"
    ADVISORY = "advisory"


class ExecutionRelation(StrEnum):
    PARENT = "parent"
    CHILD = "child"
    RETRY = "retry"
    REPLAY = "replay"
    ROLLBACK = "rollback"
    DERIVED = "derived"
    COUNTERFACTUAL = "counterfactual"
    PARALLEL = "parallel"


class ProjectId(StrEnum):
    POUPI_CRYPTO = "poupi_crypto"
    POUPI_BABY = "poupi_baby"
    SINALO = "sinalo"
    MIRROR = "mirror"
    NBA = "nba"
    WNBA = "wnba"
    JOBS = "jobs"
    REAL_ESTATE = "real_estate"
    BUSINESS_OS = "business_os"
    UNKNOWN = "unknown"


# ── Core canonical contract ────────────────────────────────────────────────────


def _uel_stable_hash(payload: dict[str, Any]) -> str:
    """Deterministic content-derived hash for execution identity."""
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:32]


def build_execution_id(
    project_id: str,
    capability_id: str,
    execution_surface: str,
    correlation_id: str,
    timestamp: datetime,
) -> str:
    return "uel:" + _uel_stable_hash(
        {
            "project_id": project_id,
            "capability_id": capability_id,
            "execution_surface": execution_surface,
            "correlation_id": correlation_id,
            "ts": timestamp.isoformat(),
        }
    )


class UELMetrics(BaseModel):
    """Latency and quality metrics captured per execution."""
    latency_ms: float = 0.0
    items_processed: int = 0
    items_failed: int = 0
    retry_count: int = 0
    cost_units: float = 0.0
    quality_score: float | None = None
    custom: dict[str, float] = Field(default_factory=dict)


class UELDecision(BaseModel):
    """Snapshot of the decision that triggered this execution."""
    decision_id: str = ""
    rationale: str = ""
    confidence: float = 0.0
    risk: float = 0.0
    approved_by: str = ""
    approval_mode: str = ""


class UELOutcome(BaseModel):
    """Snapshot of the execution result."""
    outcome_id: str = ""
    summary: str = ""
    value_delivered: bool = False
    artifacts: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    rollback_available: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)


class ExecutionLineage(BaseModel):
    """Full provenance chain for this execution."""
    mission_id: str = ""
    portfolio_id: str = ""
    opportunity_id: str = ""
    plan_id: str = ""
    decision_id: str = ""
    simulation_id: str = ""
    parent_execution_id: str = ""
    correlation_id: str = ""
    lineage_hash: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.lineage_hash:
            self.lineage_hash = _uel_stable_hash(
                {
                    "mission_id": self.mission_id,
                    "portfolio_id": self.portfolio_id,
                    "plan_id": self.plan_id,
                    "decision_id": self.decision_id,
                    "parent_execution_id": self.parent_execution_id,
                    "correlation_id": self.correlation_id,
                }
            )


class UniversalExecution(BaseModel):
    """
    Canonical execution record for the Business OS ecosystem.

    This is the single contract that represents any execution — trading signal,
    SEO run, content publish, analytics job, manual review, API call, or any
    future surface. All projects emit into this contract. None own it.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    execution_id: str
    schema_version: str = UEL_SCHEMA_VERSION

    # ── Lineage ───────────────────────────────────────────────────────────────
    mission_id: str = ""
    portfolio_id: str = ""
    project_id: str = ProjectId.UNKNOWN
    capability_id: str = ""
    lineage: ExecutionLineage = Field(default_factory=ExecutionLineage)

    # ── Surface & type ────────────────────────────────────────────────────────
    execution_surface: ExecutionSurface = ExecutionSurface.UNKNOWN
    execution_type: ExecutionType = ExecutionType.UNKNOWN

    # ── Actors ────────────────────────────────────────────────────────────────
    actor: str = ""
    planner: str = ""
    reviewer: str = ""
    executor: str = ""

    # ── Correlation ───────────────────────────────────────────────────────────
    execution_plan_id: str = ""
    correlation_id: str = ""
    parent_execution_id: str = ""
    relation: ExecutionRelation | None = None

    # ── Timing ────────────────────────────────────────────────────────────────
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: float = 0.0

    # ── State ─────────────────────────────────────────────────────────────────
    status: UELStatus = UELStatus.PLANNED
    decision: UELDecision = Field(default_factory=UELDecision)
    outcome: UELOutcome = Field(default_factory=UELOutcome)

    # ── Evidence & learning ───────────────────────────────────────────────────
    evidence_ids: list[str] = Field(default_factory=list)
    knowledge_ids: list[str] = Field(default_factory=list)
    learning_ids: list[str] = Field(default_factory=list)

    # ── Metrics ───────────────────────────────────────────────────────────────
    metrics: UELMetrics = Field(default_factory=UELMetrics)

    # ── Tags ──────────────────────────────────────────────────────────────────
    tags: dict[str, str] = Field(default_factory=dict)

    # ── UEL version metadata ──────────────────────────────────────────────────
    uel_version: str = UEL_VERSION


# ── Mutation requests ─────────────────────────────────────────────────────────


class EmitExecutionRequest(BaseModel):
    project_id: str
    capability_id: str
    execution_surface: ExecutionSurface
    execution_type: ExecutionType
    actor: str
    executor: str = ""
    planner: str = ""
    reviewer: str = ""
    mission_id: str = ""
    portfolio_id: str = ""
    correlation_id: str = ""
    parent_execution_id: str = ""
    relation: ExecutionRelation | None = None
    execution_plan_id: str = ""
    decision: UELDecision = Field(default_factory=UELDecision)
    tags: dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CompleteExecutionRequest(BaseModel):
    execution_id: str
    outcome: UELOutcome
    metrics: UELMetrics = Field(default_factory=UELMetrics)
    finished_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FailExecutionRequest(BaseModel):
    execution_id: str
    error: str
    errors: list[str] = Field(default_factory=list)
    metrics: UELMetrics = Field(default_factory=UELMetrics)
    finished_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RollbackExecutionRequest(BaseModel):
    execution_id: str
    rollback_reason: str
    rollback_target_id: str = ""
    finished_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AttachRequest(BaseModel):
    execution_id: str
    ids: list[str]


# ── Query contracts ───────────────────────────────────────────────────────────


class ExecutionQuery(BaseModel):
    project_id: str | None = None
    mission_id: str | None = None
    capability_id: str | None = None
    execution_surface: ExecutionSurface | None = None
    status: UELStatus | None = None
    actor: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int = 100
    offset: int = 0


class UELDashboardReport(BaseModel):
    """Aggregated view for the UEL dashboard."""
    total: int = 0
    by_project: dict[str, int] = Field(default_factory=dict)
    by_capability: dict[str, int] = Field(default_factory=dict)
    by_mission: dict[str, int] = Field(default_factory=dict)
    by_surface: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    avg_duration_ms: float = 0.0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    rollback_rate: float = 0.0
    shadow_count: int = 0
    simulation_count: int = 0
    total_evidence_attached: int = 0
    total_learnings_attached: int = 0
    schema_version: str = UEL_SCHEMA_VERSION
    uel_version: str = UEL_VERSION
