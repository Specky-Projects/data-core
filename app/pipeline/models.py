"""SQLAlchemy models for pipeline run observability.

Tables
──────
• ``pipeline_runs``     — one row per domain×stage execution (collection,
                          normalization, analytics).  Tracks start/end time,
                          item counts and final status.
• ``pipeline_failures`` — one row per failed run with full error context,
                          traceback and retry information.

These tables are the persistence layer behind the operational Grafana
dashboard and the ``/api/v1/operations/pipeline/runs`` endpoint.

Relationship
────────────
  pipeline_runs 1──* pipeline_failures
  (a run may accumulate multiple failures if it partially recovers)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PipelineRun(Base):
    """Records a single execution of a pipeline stage for a given domain.

    Lifecycle
    ---------
    1. Row inserted with status='running' when stage starts.
    2. Row updated with status='success'|'partial'|'error' when stage ends.
    3. ``finished_at`` and ``duration_seconds`` filled on completion.
    4. Item counters updated inline.

    Status values
    -------------
    running   — stage in progress
    success   — completed without errors
    partial   — completed but some items failed (items_error > 0)
    error     — stage itself raised an exception; no items processed
    """

    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Identity ──────────────────────────────────────────────────────────────
    domain: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Pipeline domain: crypto | ecommerce | real_estate | sports_betting | trading",
    )
    stage: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="Pipeline stage: collection | normalization | analytics",
    )
    # Optional sub-identifier (e.g. collector name, normalizer class)
    source_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # ── Timing ────────────────────────────────────────────────────────────────
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="running",
        index=True,
        comment="running | success | partial | error",
    )

    # ── Counters ──────────────────────────────────────────────────────────────
    items_input: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_error: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Optional context ──────────────────────────────────────────────────────
    trigger: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="scheduler | api | manual",
    )
    extra_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Relations ─────────────────────────────────────────────────────────────
    failures: Mapped[list[PipelineFailure]] = relationship(
        "PipelineFailure", back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_pipeline_runs_domain_stage_started", "domain", "stage", "started_at"),
        Index("ix_pipeline_runs_status_started", "status", "started_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<PipelineRun id={self.id} domain={self.domain!r} "
            f"stage={self.stage!r} status={self.status!r}>"
        )


class PipelineFailure(Base):
    """Records a single failure event within a pipeline run.

    A run may emit multiple failures (e.g. one per item that raised an
    exception).  Each failure captures the full error context for diagnosis.
    """

    __tablename__ = "pipeline_failures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Link to parent run ────────────────────────────────────────────────────
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run: Mapped[PipelineRun] = relationship("PipelineRun", back_populates="failures")

    # ── Denormalised identity (fast queries without join) ─────────────────────
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)

    # ── Error detail ──────────────────────────────────────────────────────────
    # Indexed via the composite "ix_pipeline_failures_error_type" below
    # (error_type is its leading column) — no separate single-column index.
    error_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Exception class name, e.g. 'UniqueViolation', 'TimeoutError'",
    )
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Item context (when failure is per-item) ───────────────────────────────
    item_id: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        comment="ID of the item that caused the failure (e.g. raw_collection.id)",
    )
    item_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Retry ─────────────────────────────────────────────────────────────────
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_terminal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True when max retries exhausted (dead-letter equivalent for pipeline)",
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, index=True
    )

    __table_args__ = (
        Index("ix_pipeline_failures_domain_occurred", "domain", "occurred_at"),
        Index("ix_pipeline_failures_error_type", "error_type", "occurred_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<PipelineFailure id={self.id} domain={self.domain!r} "
            f"error_type={self.error_type!r} terminal={self.is_terminal}>"
        )
