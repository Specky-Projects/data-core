"""Business OS 5.0 — UEL Ledger Protocol.

Defines the shared interface that both UELRepository (in-memory) and
UELDBRepository (SQLAlchemy) must satisfy. Any component that consumes
the UEL accepts this Protocol — no concrete coupling to either implementation.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.universal_execution_log.models import (
    AttachRequest,
    CompleteExecutionRequest,
    ExecutionQuery,
    FailExecutionRequest,
    RollbackExecutionRequest,
    UELDashboardReport,
    UniversalExecution,
)


@runtime_checkable
class UELLedgerProtocol(Protocol):
    """Structural contract for UEL read/write operations."""

    # ── Write ─────────────────────────────────────────────────────────────────

    def emit_execution(self, req: object) -> UniversalExecution: ...

    def complete_execution(self, req: CompleteExecutionRequest) -> UniversalExecution: ...

    def fail_execution(self, req: FailExecutionRequest) -> UniversalExecution: ...

    def rollback_execution(self, req: RollbackExecutionRequest) -> UniversalExecution: ...

    def attach_evidence(self, req: AttachRequest) -> UniversalExecution: ...

    def attach_knowledge(self, req: AttachRequest) -> UniversalExecution: ...

    def attach_learning(self, req: AttachRequest) -> UniversalExecution: ...

    # ── Read ──────────────────────────────────────────────────────────────────

    def query_execution(self, execution_id: str) -> UniversalExecution | None: ...

    def query_executions(self, query: ExecutionQuery) -> list[UniversalExecution]: ...

    def query_by_mission(self, mission_id: str) -> list[UniversalExecution]: ...

    def query_by_capability(self, capability_id: str) -> list[UniversalExecution]: ...

    def query_children(self, parent_execution_id: str) -> list[UniversalExecution]: ...

    def dashboard(self) -> UELDashboardReport: ...
