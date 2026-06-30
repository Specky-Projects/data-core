"""Business OS 5.0 — Universal Execution Log repository (in-memory).

This repository operates over UniversalExecution DTOs (not ORM rows) so that
it can be used in tests and dry-run contexts without a database connection.
For database persistence use UELDBRepository (requires SQLAlchemy session).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.universal_execution_log.models import (
    AttachRequest,
    CompleteExecutionRequest,
    EmitExecutionRequest,
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
    UniversalExecution,
    UEL_SCHEMA_VERSION,
    build_execution_id,
)


class UELRepository:
    """In-memory canonical execution store.

    Holds executions for one session / replay context. Thread-unsafe by design
    — wrap with a lock if used across threads. Immutable once emitted (status
    transitions are the only allowed mutations via the public API).
    """

    def __init__(self) -> None:
        self._store: dict[str, UniversalExecution] = {}

    # ── Write API ─────────────────────────────────────────────────────────────

    def emit_execution(self, req: EmitExecutionRequest) -> UniversalExecution:
        """Register a new execution. Returns the canonical record."""
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
        execution = UniversalExecution(
            execution_id=execution_id,
            schema_version=UEL_SCHEMA_VERSION,
            mission_id=req.mission_id,
            portfolio_id=req.portfolio_id,
            project_id=req.project_id,
            capability_id=req.capability_id,
            lineage=lineage,
            execution_surface=req.execution_surface,
            execution_type=req.execution_type,
            actor=req.actor,
            planner=req.planner,
            reviewer=req.reviewer,
            executor=req.executor,
            execution_plan_id=req.execution_plan_id,
            correlation_id=req.correlation_id,
            parent_execution_id=req.parent_execution_id,
            relation=req.relation,
            timestamp=req.timestamp,
            started_at=req.timestamp,
            status=UELStatus.PLANNED,
            decision=req.decision,
            tags=req.tags,
        )
        self._store[execution_id] = execution
        return execution

    def complete_execution(self, req: CompleteExecutionRequest) -> UniversalExecution:
        execution = self._require(req.execution_id)
        started = execution.started_at or execution.timestamp
        duration_ms = (req.finished_at - started).total_seconds() * 1000
        updated = execution.model_copy(
            update={
                "status": UELStatus.SUCCESS,
                "outcome": req.outcome,
                "metrics": req.metrics,
                "finished_at": req.finished_at,
                "duration_ms": duration_ms,
            }
        )
        self._store[req.execution_id] = updated
        return updated

    def fail_execution(self, req: FailExecutionRequest) -> UniversalExecution:
        execution = self._require(req.execution_id)
        started = execution.started_at or execution.timestamp
        duration_ms = (req.finished_at - started).total_seconds() * 1000
        outcome = UELOutcome(
            summary=req.error,
            value_delivered=False,
            errors=[req.error] + req.errors,
        )
        updated = execution.model_copy(
            update={
                "status": UELStatus.FAILED,
                "outcome": outcome,
                "metrics": req.metrics,
                "finished_at": req.finished_at,
                "duration_ms": duration_ms,
            }
        )
        self._store[req.execution_id] = updated
        return updated

    def rollback_execution(self, req: RollbackExecutionRequest) -> UniversalExecution:
        execution = self._require(req.execution_id)
        started = execution.started_at or execution.timestamp
        duration_ms = (req.finished_at - started).total_seconds() * 1000
        outcome = UELOutcome(
            summary=req.rollback_reason,
            value_delivered=False,
            rollback_available=True,
            artifacts=[req.rollback_target_id] if req.rollback_target_id else [],
        )
        updated = execution.model_copy(
            update={
                "status": UELStatus.ROLLBACK,
                "outcome": outcome,
                "finished_at": req.finished_at,
                "duration_ms": duration_ms,
                "relation": ExecutionRelation.ROLLBACK,
            }
        )
        self._store[req.execution_id] = updated
        return updated

    def attach_evidence(self, req: AttachRequest) -> UniversalExecution:
        execution = self._require(req.execution_id)
        updated_ids = list(dict.fromkeys(execution.evidence_ids + req.ids))
        updated = execution.model_copy(update={"evidence_ids": updated_ids})
        self._store[req.execution_id] = updated
        return updated

    def attach_knowledge(self, req: AttachRequest) -> UniversalExecution:
        execution = self._require(req.execution_id)
        updated_ids = list(dict.fromkeys(execution.knowledge_ids + req.ids))
        updated = execution.model_copy(update={"knowledge_ids": updated_ids})
        self._store[req.execution_id] = updated
        return updated

    def attach_learning(self, req: AttachRequest) -> UniversalExecution:
        execution = self._require(req.execution_id)
        updated_ids = list(dict.fromkeys(execution.learning_ids + req.ids))
        updated = execution.model_copy(update={"learning_ids": updated_ids})
        self._store[req.execution_id] = updated
        return updated

    # ── Read API ──────────────────────────────────────────────────────────────

    def query_execution(self, execution_id: str) -> UniversalExecution | None:
        return self._store.get(execution_id)

    def query_executions(self, query: ExecutionQuery) -> list[UniversalExecution]:
        results = list(self._store.values())

        if query.project_id is not None:
            results = [e for e in results if e.project_id == query.project_id]
        if query.mission_id is not None:
            results = [e for e in results if e.mission_id == query.mission_id]
        if query.capability_id is not None:
            results = [e for e in results if e.capability_id == query.capability_id]
        if query.execution_surface is not None:
            results = [e for e in results if e.execution_surface == query.execution_surface]
        if query.status is not None:
            results = [e for e in results if e.status == query.status]
        if query.actor is not None:
            results = [e for e in results if e.actor == query.actor]
        if query.since is not None:
            results = [e for e in results if e.timestamp >= query.since]
        if query.until is not None:
            results = [e for e in results if e.timestamp <= query.until]

        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[query.offset : query.offset + query.limit]

    def query_by_mission(self, mission_id: str) -> list[UniversalExecution]:
        return self.query_executions(ExecutionQuery(mission_id=mission_id, limit=1000))

    def query_by_capability(self, capability_id: str) -> list[UniversalExecution]:
        return self.query_executions(ExecutionQuery(capability_id=capability_id, limit=1000))

    def query_children(self, parent_execution_id: str) -> list[UniversalExecution]:
        return [
            e for e in self._store.values()
            if e.parent_execution_id == parent_execution_id
        ]

    def dashboard(self) -> UELDashboardReport:
        executions = list(self._store.values())
        total = len(executions)
        if total == 0:
            return UELDashboardReport(total=0)

        by_project: dict[str, int] = {}
        by_capability: dict[str, int] = {}
        by_mission: dict[str, int] = {}
        by_surface: dict[str, int] = {}
        by_status: dict[str, int] = {}
        total_duration = 0.0
        total_evidence = 0
        total_learnings = 0
        success = 0
        failed = 0
        rollback = 0
        shadow = 0
        simulation = 0

        for e in executions:
            by_project[e.project_id] = by_project.get(e.project_id, 0) + 1
            by_capability[e.capability_id] = by_capability.get(e.capability_id, 0) + 1
            if e.mission_id:
                by_mission[e.mission_id] = by_mission.get(e.mission_id, 0) + 1
            by_surface[e.execution_surface] = by_surface.get(e.execution_surface, 0) + 1
            by_status[e.status] = by_status.get(e.status, 0) + 1
            total_duration += e.duration_ms
            total_evidence += len(e.evidence_ids)
            total_learnings += len(e.learning_ids)
            if e.status == UELStatus.SUCCESS:
                success += 1
            elif e.status == UELStatus.FAILED:
                failed += 1
            elif e.status == UELStatus.ROLLBACK:
                rollback += 1
            elif e.status == UELStatus.SHADOW:
                shadow += 1
            elif e.status == UELStatus.SIMULATION:
                simulation += 1

        return UELDashboardReport(
            total=total,
            by_project=by_project,
            by_capability=by_capability,
            by_mission=by_mission,
            by_surface=by_surface,
            by_status=by_status,
            avg_duration_ms=total_duration / total,
            success_rate=success / total,
            failure_rate=failed / total,
            rollback_rate=rollback / total,
            shadow_count=shadow,
            simulation_count=simulation,
            total_evidence_attached=total_evidence,
            total_learnings_attached=total_learnings,
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _require(self, execution_id: str) -> UniversalExecution:
        execution = self._store.get(execution_id)
        if execution is None:
            raise KeyError(f"UEL: execution not found: {execution_id}")
        return execution

    def __len__(self) -> int:
        return len(self._store)
