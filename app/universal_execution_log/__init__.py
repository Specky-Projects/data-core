"""Business OS 5.0 — Universal Execution Log (UEL).

The UEL is the canonical flight-recorder for the entire Business OS ecosystem.
Every project emits executions into this single contract; none own it.

Quick usage:

    from app.universal_execution_log import CryptoUELAdapter, UELRepository

    repo = UELRepository()
    adapter = CryptoUELAdapter(repo)

    execution = adapter.emit_signal("edge:btc-momentum", signal_id="sig-001")
    adapter.complete(execution.execution_id, summary="Signal produced", value_delivered=True)
    report = repo.dashboard()
"""

from app.universal_execution_log.adapters import (
    BabyUELAdapter,
    BusinessOSUELAdapter,
    CryptoUELAdapter,
    SinaloUELAdapter,
    UELAdapter,
)
from app.universal_execution_log.models import (
    AttachRequest,
    CompleteExecutionRequest,
    EmitExecutionRequest,
    ExecutionLineage,
    ExecutionQuery,
    ExecutionRelation,
    ExecutionSurface,
    ExecutionType,
    FailExecutionRequest,
    ProjectId,
    RollbackExecutionRequest,
    UELDashboardReport,
    UELDecision,
    UELMetrics,
    UELOutcome,
    UEL_SCHEMA_VERSION,
    UEL_VERSION,
    UELStatus,
    UniversalExecution,
    build_execution_id,
)
from app.universal_execution_log.health import UELHealthReport, compute_uel_health
from app.universal_execution_log.ledger import LEDGER_VERSION, UELDBRepository
from app.universal_execution_log.protocol import UELLedgerProtocol
from app.universal_execution_log.repository import UELRepository
from app.universal_execution_log.scientific_bridge import ScientificLedgerBridge

__all__ = [
    # models
    "UEL_VERSION",
    "UEL_SCHEMA_VERSION",
    "ExecutionSurface",
    "ExecutionType",
    "UELStatus",
    "ExecutionRelation",
    "ProjectId",
    "UELMetrics",
    "UELDecision",
    "UELOutcome",
    "ExecutionLineage",
    "UniversalExecution",
    "EmitExecutionRequest",
    "CompleteExecutionRequest",
    "FailExecutionRequest",
    "RollbackExecutionRequest",
    "AttachRequest",
    "ExecutionQuery",
    "UELDashboardReport",
    "build_execution_id",
    # repository (in-memory)
    "UELRepository",
    # ledger (SQLAlchemy-backed)
    "LEDGER_VERSION",
    "UELDBRepository",
    # protocol
    "UELLedgerProtocol",
    # scientific bridge
    "ScientificLedgerBridge",
    # health
    "UELHealthReport",
    "compute_uel_health",
    # adapters
    "UELAdapter",
    "CryptoUELAdapter",
    "BabyUELAdapter",
    "SinaloUELAdapter",
    "BusinessOSUELAdapter",
]
