"""Business OS 5.0 — Universal Execution Ledger (SQLAlchemy-backed).

UELDBRepository is the production-grade implementation of the UEL.
It persists every execution to the `universal_executions` table, provides
transactional safety, and exposes efficient SQL-level aggregation for the
dashboard.

Immutability contract: status transitions are the ONLY allowed mutations.
Decision, lineage, and identity fields are write-once (enforced at API level).

Usage:

    from database.session import SessionLocal
    from app.universal_execution_log.ledger import UELDBRepository

    with SessionLocal() as session:
        repo = UELDBRepository(session)
        e = repo.emit_execution(req)
        session.commit()
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.universal_execution_log.db_models import UniversalExecutionRecord
from app.universal_execution_log.models import (
    AttachRequest,
    CompleteExecutionRequest,
    ExecutionLineage,
    ExecutionQuery,
    ExecutionRelation,
    FailExecutionRequest,
    RollbackExecutionRequest,
    UELDashboardReport,
    UELDecision,
    UELMetrics,
    UELOutcome,
    UELStatus,
    UEL_SCHEMA_VERSION,
    UEL_VERSION,
    EmitExecutionRequest,
    UniversalExecution,
    build_execution_id,
)

LEDGER_VERSION = "business-os-5.1-universal-execution-ledger"


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; restore UTC so arithmetic is always tz-aware."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ── DTO ↔ ORM converters ──────────────────────────────────────────────────────


def _record_to_dto(r: UniversalExecutionRecord) -> UniversalExecution:
    lineage_data = r.lineage if isinstance(r.lineage, dict) else {}
    ts = _ensure_utc(r.timestamp) or datetime.now(timezone.utc)
    return UniversalExecution(
        execution_id=r.execution_id,
        schema_version=r.schema_version,
        mission_id=r.mission_id or "",
        portfolio_id=r.portfolio_id or "",
        project_id=r.project_id,
        capability_id=r.capability_id,
        lineage=ExecutionLineage(**lineage_data) if lineage_data else ExecutionLineage(),
        execution_surface=r.execution_surface,  # type: ignore[arg-type]
        execution_type=r.execution_type,  # type: ignore[arg-type]
        actor=r.actor or "",
        planner=r.planner or "",
        reviewer=r.reviewer or "",
        executor=r.executor or "",
        execution_plan_id=r.execution_plan_id or "",
        correlation_id=r.correlation_id or "",
        parent_execution_id=r.parent_execution_id or "",
        relation=r.relation,  # type: ignore[arg-type]
        timestamp=ts,
        started_at=_ensure_utc(r.started_at),
        finished_at=_ensure_utc(r.finished_at),
        duration_ms=r.duration_ms,
        status=r.status,  # type: ignore[arg-type]
        decision=UELDecision(**(r.decision if isinstance(r.decision, dict) else {})),
        outcome=UELOutcome(**(r.outcome if isinstance(r.outcome, dict) else {})),
        evidence_ids=list(r.evidence_ids) if r.evidence_ids else [],
        knowledge_ids=list(r.knowledge_ids) if r.knowledge_ids else [],
        learning_ids=list(r.learning_ids) if r.learning_ids else [],
        metrics=UELMetrics(**(r.metrics if isinstance(r.metrics, dict) else {})),
        tags=dict(r.tags) if r.tags else {},
        uel_version=r.uel_version,
    )


def _emit_req_to_record(req: EmitExecutionRequest) -> UniversalExecutionRecord:
    execution_id = build_execution_id(
        project_id=req.project_id,
        capability_id=req.capability_id,
        execution_surface=req.execution_surface.value,
        correlation_id=req.correlation_id or req.capability_id,
        timestamp=req.timestamp,
    )
    lineage = ExecutionLineage(
        mission_id=req.mission_id,
        portfolio_id=req.portfolio_id,
        plan_id=req.execution_plan_id,
        decision_id=req.decision.decision_id,
        parent_execution_id=req.parent_execution_id,
        correlation_id=req.correlation_id,
    )
    return UniversalExecutionRecord(
        id=uuid.uuid4(),
        execution_id=execution_id,
        schema_version=UEL_SCHEMA_VERSION,
        mission_id=req.mission_id or None,
        portfolio_id=req.portfolio_id or None,
        project_id=req.project_id,
        capability_id=req.capability_id,
        lineage=lineage.model_dump(),
        execution_surface=req.execution_surface.value,
        execution_type=req.execution_type.value,
        actor=req.actor or None,
        planner=req.planner or None,
        reviewer=req.reviewer or None,
        executor=req.executor or None,
        execution_plan_id=req.execution_plan_id or None,
        correlation_id=req.correlation_id or None,
        parent_execution_id=req.parent_execution_id or None,
        relation=req.relation.value if req.relation else None,
        timestamp=req.timestamp,
        started_at=req.timestamp,
        status=UELStatus.PLANNED.value,
        decision=req.decision.model_dump(),
        outcome={},
        evidence_ids=[],
        knowledge_ids=[],
        learning_ids=[],
        metrics=UELMetrics().model_dump(),
        tags=req.tags,
        uel_version=UEL_VERSION,
    )


# ── Repository ────────────────────────────────────────────────────────────────


class UELDBRepository:
    """Production SQLAlchemy-backed Universal Execution Ledger.

    Every operation is wrapped in the caller's session transaction.
    Call session.commit() after mutations. The repository itself does NOT
    commit — it only adds/updates ORM objects and lets the caller decide
    the transaction boundary (unit-of-work pattern).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Write ─────────────────────────────────────────────────────────────────

    def emit_execution(self, req: EmitExecutionRequest) -> UniversalExecution:
        """Insert a new canonical execution record. Idempotent on execution_id."""
        record = _emit_req_to_record(req)
        existing = self._session.execute(
            select(UniversalExecutionRecord).where(
                UniversalExecutionRecord.execution_id == record.execution_id
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _record_to_dto(existing)
        self._session.add(record)
        self._session.flush()
        return _record_to_dto(record)

    def complete_execution(self, req: CompleteExecutionRequest) -> UniversalExecution:
        record = self._require(req.execution_id)
        started = _ensure_utc(record.started_at or record.timestamp)
        duration_ms = (req.finished_at - started).total_seconds() * 1000
        record.status = UELStatus.SUCCESS.value
        record.outcome = req.outcome.model_dump()
        record.metrics = req.metrics.model_dump()
        record.finished_at = req.finished_at
        record.duration_ms = duration_ms
        self._session.flush()
        return _record_to_dto(record)

    def fail_execution(self, req: FailExecutionRequest) -> UniversalExecution:
        record = self._require(req.execution_id)
        started = _ensure_utc(record.started_at or record.timestamp)
        duration_ms = (req.finished_at - started).total_seconds() * 1000
        outcome = UELOutcome(
            summary=req.error,
            value_delivered=False,
            errors=[req.error] + req.errors,
        )
        record.status = UELStatus.FAILED.value
        record.outcome = outcome.model_dump()
        record.metrics = req.metrics.model_dump()
        record.finished_at = req.finished_at
        record.duration_ms = duration_ms
        self._session.flush()
        return _record_to_dto(record)

    def rollback_execution(self, req: RollbackExecutionRequest) -> UniversalExecution:
        record = self._require(req.execution_id)
        started = _ensure_utc(record.started_at or record.timestamp)
        duration_ms = (req.finished_at - started).total_seconds() * 1000
        outcome = UELOutcome(
            summary=req.rollback_reason,
            value_delivered=False,
            rollback_available=True,
            artifacts=[req.rollback_target_id] if req.rollback_target_id else [],
        )
        record.status = UELStatus.ROLLBACK.value
        record.outcome = outcome.model_dump()
        record.relation = ExecutionRelation.ROLLBACK.value
        record.finished_at = req.finished_at
        record.duration_ms = duration_ms
        self._session.flush()
        return _record_to_dto(record)

    def attach_evidence(self, req: AttachRequest) -> UniversalExecution:
        record = self._require(req.execution_id)
        current = list(record.evidence_ids or [])
        updated = list(dict.fromkeys(current + req.ids))
        record.evidence_ids = updated
        self._session.flush()
        return _record_to_dto(record)

    def attach_knowledge(self, req: AttachRequest) -> UniversalExecution:
        record = self._require(req.execution_id)
        current = list(record.knowledge_ids or [])
        updated = list(dict.fromkeys(current + req.ids))
        record.knowledge_ids = updated
        self._session.flush()
        return _record_to_dto(record)

    def attach_learning(self, req: AttachRequest) -> UniversalExecution:
        record = self._require(req.execution_id)
        current = list(record.learning_ids or [])
        updated = list(dict.fromkeys(current + req.ids))
        record.learning_ids = updated
        self._session.flush()
        return _record_to_dto(record)

    # ── Read ──────────────────────────────────────────────────────────────────

    def query_execution(self, execution_id: str) -> UniversalExecution | None:
        record = self._session.execute(
            select(UniversalExecutionRecord).where(
                UniversalExecutionRecord.execution_id == execution_id
            )
        ).scalar_one_or_none()
        return _record_to_dto(record) if record else None

    def query_executions(self, query: ExecutionQuery) -> list[UniversalExecution]:
        stmt = select(UniversalExecutionRecord)
        if query.project_id is not None:
            stmt = stmt.where(UniversalExecutionRecord.project_id == query.project_id)
        if query.mission_id is not None:
            stmt = stmt.where(UniversalExecutionRecord.mission_id == query.mission_id)
        if query.capability_id is not None:
            stmt = stmt.where(UniversalExecutionRecord.capability_id == query.capability_id)
        if query.execution_surface is not None:
            stmt = stmt.where(UniversalExecutionRecord.execution_surface == query.execution_surface.value)
        if query.status is not None:
            stmt = stmt.where(UniversalExecutionRecord.status == query.status.value)
        if query.actor is not None:
            stmt = stmt.where(UniversalExecutionRecord.actor == query.actor)
        if query.since is not None:
            stmt = stmt.where(UniversalExecutionRecord.timestamp >= query.since)
        if query.until is not None:
            stmt = stmt.where(UniversalExecutionRecord.timestamp <= query.until)
        stmt = stmt.order_by(UniversalExecutionRecord.timestamp.desc())
        stmt = stmt.offset(query.offset).limit(query.limit)
        records = self._session.execute(stmt).scalars().all()
        return [_record_to_dto(r) for r in records]

    def query_by_mission(self, mission_id: str) -> list[UniversalExecution]:
        return self.query_executions(ExecutionQuery(mission_id=mission_id, limit=1000))

    def query_by_capability(self, capability_id: str) -> list[UniversalExecution]:
        return self.query_executions(ExecutionQuery(capability_id=capability_id, limit=1000))

    def query_children(self, parent_execution_id: str) -> list[UniversalExecution]:
        records = self._session.execute(
            select(UniversalExecutionRecord).where(
                UniversalExecutionRecord.parent_execution_id == parent_execution_id
            )
        ).scalars().all()
        return [_record_to_dto(r) for r in records]

    def dashboard(self) -> UELDashboardReport:
        """SQL-level aggregation — no Python-side full-table iteration."""
        total = self._session.execute(
            select(func.count()).select_from(UniversalExecutionRecord)
        ).scalar() or 0

        if total == 0:
            return UELDashboardReport(total=0)

        # ── By project ────────────────────────────────────────────────────────
        by_project: dict[str, int] = {
            row[0]: row[1]
            for row in self._session.execute(
                select(UniversalExecutionRecord.project_id, func.count())
                .group_by(UniversalExecutionRecord.project_id)
            ).all()
        }

        # ── By capability ─────────────────────────────────────────────────────
        by_capability: dict[str, int] = {
            row[0]: row[1]
            for row in self._session.execute(
                select(UniversalExecutionRecord.capability_id, func.count())
                .group_by(UniversalExecutionRecord.capability_id)
            ).all()
        }

        # ── By mission ────────────────────────────────────────────────────────
        by_mission: dict[str, int] = {
            row[0]: row[1]
            for row in self._session.execute(
                select(UniversalExecutionRecord.mission_id, func.count())
                .where(UniversalExecutionRecord.mission_id.is_not(None))
                .group_by(UniversalExecutionRecord.mission_id)
            ).all()
        }

        # ── By surface ────────────────────────────────────────────────────────
        by_surface: dict[str, int] = {
            row[0]: row[1]
            for row in self._session.execute(
                select(UniversalExecutionRecord.execution_surface, func.count())
                .group_by(UniversalExecutionRecord.execution_surface)
            ).all()
        }

        # ── By status ─────────────────────────────────────────────────────────
        by_status: dict[str, int] = {
            row[0]: row[1]
            for row in self._session.execute(
                select(UniversalExecutionRecord.status, func.count())
                .group_by(UniversalExecutionRecord.status)
            ).all()
        }

        # ── Averages and counts ───────────────────────────────────────────────
        avg_duration = self._session.execute(
            select(func.avg(UniversalExecutionRecord.duration_ms))
        ).scalar() or 0.0

        success = by_status.get(UELStatus.SUCCESS.value, 0)
        failed = by_status.get(UELStatus.FAILED.value, 0)
        rollback = by_status.get(UELStatus.ROLLBACK.value, 0)
        shadow = by_status.get(UELStatus.SHADOW.value, 0)
        simulation = by_status.get(UELStatus.SIMULATION.value, 0)

        # ── Evidence / learning aggregation via JSON array length ─────────────
        # Works on PostgreSQL; graceful fallback for SQLite
        try:
            total_evidence = self._session.execute(
                text(
                    "SELECT COALESCE(SUM(jsonb_array_length(evidence_ids)), 0) "
                    "FROM universal_executions"
                )
            ).scalar() or 0
            total_learnings = self._session.execute(
                text(
                    "SELECT COALESCE(SUM(jsonb_array_length(learning_ids)), 0) "
                    "FROM universal_executions"
                )
            ).scalar() or 0
        except Exception:
            total_evidence = 0
            total_learnings = 0

        return UELDashboardReport(
            total=total,
            by_project=by_project,
            by_capability=by_capability,
            by_mission=by_mission,
            by_surface=by_surface,
            by_status=by_status,
            avg_duration_ms=float(avg_duration),
            success_rate=success / total if total else 0.0,
            failure_rate=failed / total if total else 0.0,
            rollback_rate=rollback / total if total else 0.0,
            shadow_count=shadow,
            simulation_count=simulation,
            total_evidence_attached=int(total_evidence),
            total_learnings_attached=int(total_learnings),
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _require(self, execution_id: str) -> UniversalExecutionRecord:
        record = self._session.execute(
            select(UniversalExecutionRecord).where(
                UniversalExecutionRecord.execution_id == execution_id
            )
        ).scalar_one_or_none()
        if record is None:
            raise KeyError(f"UEL Ledger: execution not found: {execution_id}")
        return record

    def __len__(self) -> int:
        return self._session.execute(
            select(func.count()).select_from(UniversalExecutionRecord)
        ).scalar() or 0
