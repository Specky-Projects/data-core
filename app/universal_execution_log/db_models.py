"""Business OS 5.0 — Universal Execution Log SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database.models import Base, JSONB_COMPAT


class UniversalExecutionRecord(Base):
    """Immutable canonical execution record — the UEL flight log row."""

    __tablename__ = "universal_executions"

    # ── Identity ──────────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    execution_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    schema_version: Mapped[str] = mapped_column(String(40), index=True)

    # ── Lineage ───────────────────────────────────────────────────────────────
    mission_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    portfolio_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    capability_id: Mapped[str] = mapped_column(String(128), index=True)
    lineage: Mapped[dict[str, Any]] = mapped_column(JSONB_COMPAT, default=dict)

    # ── Surface & type ────────────────────────────────────────────────────────
    execution_surface: Mapped[str] = mapped_column(String(64), index=True)
    execution_type: Mapped[str] = mapped_column(String(64), index=True)

    # ── Actors ────────────────────────────────────────────────────────────────
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    planner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    executor: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # ── Correlation ───────────────────────────────────────────────────────────
    execution_plan_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    parent_execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    relation: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # ── Timing ────────────────────────────────────────────────────────────────
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)

    # ── State ─────────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(String(32), index=True)
    decision: Mapped[dict[str, Any]] = mapped_column(JSONB_COMPAT, default=dict)
    outcome: Mapped[dict[str, Any]] = mapped_column(JSONB_COMPAT, default=dict)

    # ── Evidence & learning ───────────────────────────────────────────────────
    evidence_ids: Mapped[list[Any]] = mapped_column(JSONB_COMPAT, default=list)
    knowledge_ids: Mapped[list[Any]] = mapped_column(JSONB_COMPAT, default=list)
    learning_ids: Mapped[list[Any]] = mapped_column(JSONB_COMPAT, default=list)

    # ── Metrics ───────────────────────────────────────────────────────────────
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB_COMPAT, default=dict)

    # ── Tags ──────────────────────────────────────────────────────────────────
    tags: Mapped[dict[str, Any]] = mapped_column(JSONB_COMPAT, default=dict)

    # ── UEL version ───────────────────────────────────────────────────────────
    uel_version: Mapped[str] = mapped_column(String(80))

    # ── Audit timestamps ──────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_uel_project_surface", "project_id", "execution_surface"),
        Index("ix_uel_project_status", "project_id", "status"),
        Index("ix_uel_mission_capability", "mission_id", "capability_id"),
        Index("ix_uel_timestamp_status", "timestamp", "status"),
        Index("ix_uel_parent", "parent_execution_id"),
        Index("ix_uel_correlation", "correlation_id"),
    )
