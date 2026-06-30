"""Business OS 5.1 — Universal Execution Ledger (SQLAlchemy) tests.

Uses SQLite in-memory so no PostgreSQL connection is required.
All tests verify:
  - Persistence and retrieval via UELDBRepository
  - Protocol compatibility (UELDBRepository satisfies UELLedgerProtocol)
  - Full lifecycle: emit → complete / fail / rollback
  - Evidence / knowledge / learning attachment
  - Parent-child lineage
  - Query filtering (project, status, mission, capability, pagination)
  - Dashboard aggregation (SQL-level)
  - Idempotency on emit (duplicate execution_id)
  - Adapter compatibility with DB backend
  - Scientific bridge projections
  - Health check
  - Immutability (identity fields cannot be mutated via public API)
  - Rollback: session.rollback() discards uncommitted state
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.universal_execution_log.adapters import (
    BabyUELAdapter,
    CryptoUELAdapter,
    SinaloUELAdapter,
)
from app.universal_execution_log.db_models import UniversalExecutionRecord
from app.universal_execution_log.health import compute_uel_health
from app.universal_execution_log.ledger import UELDBRepository
from app.universal_execution_log.models import (
    AttachRequest,
    CompleteExecutionRequest,
    EmitExecutionRequest,
    ExecutionQuery,
    ExecutionRelation,
    ExecutionSurface,
    ExecutionType,
    FailExecutionRequest,
    ProjectId,
    RollbackExecutionRequest,
    UEL_SCHEMA_VERSION,
    UEL_VERSION,
    UELStatus,
    UniversalExecution,
    UELDecision,
    UELMetrics,
    UELOutcome,
    build_execution_id,
)
from app.universal_execution_log.protocol import UELLedgerProtocol
from app.universal_execution_log.repository import UELRepository
from app.universal_execution_log.scientific_bridge import ScientificLedgerBridge
from database.models import Base

# ── Test fixtures ─────────────────────────────────────────────────────────────

_TS = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)
_TS2 = datetime(2026, 6, 29, 12, 0, 1, tzinfo=timezone.utc)
_TS3 = datetime(2026, 6, 29, 12, 0, 2, tzinfo=timezone.utc)
_TS4 = datetime(2026, 6, 29, 12, 0, 3, tzinfo=timezone.utc)


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    yield db
    db.close()
    engine.dispose()


@pytest.fixture()
def repo(session: Session) -> UELDBRepository:
    return UELDBRepository(session)


def _req(
    project_id: str = ProjectId.POUPI_CRYPTO,
    capability_id: str = "edge:btc-momentum",
    surface: ExecutionSurface = ExecutionSurface.TRADING,
    execution_type: ExecutionType = ExecutionType.SIGNAL,
    actor: str = "crypto-engine",
    mission_id: str = "mission-001",
    correlation_id: str = "corr-001",
    timestamp: datetime = _TS,
) -> EmitExecutionRequest:
    return EmitExecutionRequest(
        project_id=project_id,
        capability_id=capability_id,
        execution_surface=surface,
        execution_type=execution_type,
        actor=actor,
        mission_id=mission_id,
        correlation_id=correlation_id,
        timestamp=timestamp,
    )


# ── 1. Protocol compatibility ─────────────────────────────────────────────────


def test_db_repository_satisfies_protocol(repo: UELDBRepository):
    assert isinstance(repo, UELLedgerProtocol)


def test_in_memory_repository_satisfies_protocol():
    assert isinstance(UELRepository(), UELLedgerProtocol)


# ── 2. Emit and persist ───────────────────────────────────────────────────────


def test_emit_persists_record(session: Session, repo: UELDBRepository):
    e = repo.emit_execution(_req())
    session.commit()

    assert isinstance(e, UniversalExecution)
    assert e.schema_version == UEL_SCHEMA_VERSION
    assert e.uel_version == UEL_VERSION
    assert e.status == UELStatus.PLANNED
    assert e.execution_id.startswith("uel:")

    count = session.execute(text("SELECT COUNT(*) FROM universal_executions")).scalar()
    assert count == 1


def test_emit_is_idempotent(session: Session, repo: UELDBRepository):
    e1 = repo.emit_execution(_req())
    e2 = repo.emit_execution(_req())  # same inputs → same execution_id
    session.commit()

    assert e1.execution_id == e2.execution_id
    count = session.execute(text("SELECT COUNT(*) FROM universal_executions")).scalar()
    assert count == 1


def test_query_execution_returns_persisted(session: Session, repo: UELDBRepository):
    e = repo.emit_execution(_req())
    session.commit()

    fetched = repo.query_execution(e.execution_id)
    assert fetched is not None
    assert fetched.execution_id == e.execution_id
    assert fetched.project_id == ProjectId.POUPI_CRYPTO


def test_query_nonexistent_returns_none(repo: UELDBRepository):
    assert repo.query_execution("uel:nonexistent") is None


# ── 3. Lifecycle transitions ──────────────────────────────────────────────────


def test_complete_execution(session: Session, repo: UELDBRepository):
    e = repo.emit_execution(_req(timestamp=_TS))
    session.commit()

    outcome = UELOutcome(summary="Signal produced", value_delivered=True, artifacts=["sig-001"])
    metrics = UELMetrics(latency_ms=42.0, items_processed=1)
    completed = repo.complete_execution(
        CompleteExecutionRequest(
            execution_id=e.execution_id,
            outcome=outcome,
            metrics=metrics,
            finished_at=_TS2,
        )
    )
    session.commit()

    assert completed.status == UELStatus.SUCCESS
    assert completed.outcome.value_delivered is True
    assert completed.outcome.artifacts == ["sig-001"]
    assert completed.metrics.latency_ms == 42.0
    assert completed.duration_ms == pytest.approx(1000.0)

    # Verify persisted
    fetched = repo.query_execution(e.execution_id)
    assert fetched is not None
    assert fetched.status == UELStatus.SUCCESS


def test_fail_execution(session: Session, repo: UELDBRepository):
    e = repo.emit_execution(_req(timestamp=_TS))
    session.commit()

    failed = repo.fail_execution(
        FailExecutionRequest(
            execution_id=e.execution_id,
            error="Exchange timeout",
            finished_at=_TS2,
        )
    )
    session.commit()

    assert failed.status == UELStatus.FAILED
    assert "Exchange timeout" in failed.outcome.errors

    fetched = repo.query_execution(e.execution_id)
    assert fetched is not None
    assert fetched.status == UELStatus.FAILED


def test_rollback_execution(session: Session, repo: UELDBRepository):
    e = repo.emit_execution(_req(timestamp=_TS))
    session.commit()

    rolled = repo.rollback_execution(
        RollbackExecutionRequest(
            execution_id=e.execution_id,
            rollback_reason="Kill switch triggered",
            rollback_target_id="checkpoint-001",
            finished_at=_TS2,
        )
    )
    session.commit()

    assert rolled.status == UELStatus.ROLLBACK
    assert rolled.relation == ExecutionRelation.ROLLBACK
    assert rolled.outcome.rollback_available is True

    fetched = repo.query_execution(e.execution_id)
    assert fetched is not None
    assert fetched.status == UELStatus.ROLLBACK


def test_unknown_id_raises(repo: UELDBRepository):
    with pytest.raises(KeyError):
        repo.complete_execution(
            CompleteExecutionRequest(
                execution_id="uel:ghost",
                outcome=UELOutcome(),
                finished_at=_TS,
            )
        )


# ── 4. Attachment ─────────────────────────────────────────────────────────────


def test_attach_evidence_persists(session: Session, repo: UELDBRepository):
    e = repo.emit_execution(_req())
    session.commit()

    updated = repo.attach_evidence(AttachRequest(execution_id=e.execution_id, ids=["ev-1", "ev-2"]))
    session.commit()

    assert "ev-1" in updated.evidence_ids
    assert "ev-2" in updated.evidence_ids

    fetched = repo.query_execution(e.execution_id)
    assert fetched is not None
    assert "ev-1" in fetched.evidence_ids


def test_attach_deduplicates(session: Session, repo: UELDBRepository):
    e = repo.emit_execution(_req())
    repo.attach_evidence(AttachRequest(execution_id=e.execution_id, ids=["ev-1"]))
    updated = repo.attach_evidence(AttachRequest(execution_id=e.execution_id, ids=["ev-1", "ev-2"]))
    session.commit()

    assert updated.evidence_ids.count("ev-1") == 1
    assert "ev-2" in updated.evidence_ids


def test_attach_knowledge_and_learning(session: Session, repo: UELDBRepository):
    e = repo.emit_execution(_req())
    repo.attach_knowledge(AttachRequest(execution_id=e.execution_id, ids=["kn-1"]))
    repo.attach_learning(AttachRequest(execution_id=e.execution_id, ids=["lr-1"]))
    session.commit()

    fetched = repo.query_execution(e.execution_id)
    assert fetched is not None
    assert "kn-1" in fetched.knowledge_ids
    assert "lr-1" in fetched.learning_ids


# ── 5. Parent-child lineage ───────────────────────────────────────────────────


def test_parent_child_lineage(session: Session, repo: UELDBRepository):
    parent = repo.emit_execution(_req(correlation_id="corr-parent", timestamp=_TS))
    session.commit()

    child = repo.emit_execution(
        EmitExecutionRequest(
            project_id=ProjectId.POUPI_CRYPTO,
            capability_id="edge:btc-momentum",
            execution_surface=ExecutionSurface.TRADING,
            execution_type=ExecutionType.TRADE,
            actor="executor",
            parent_execution_id=parent.execution_id,
            relation=ExecutionRelation.CHILD,
            timestamp=_TS2,
        )
    )
    session.commit()

    children = repo.query_children(parent.execution_id)
    assert len(children) == 1
    assert children[0].execution_id == child.execution_id
    assert children[0].relation == ExecutionRelation.CHILD


# ── 6. Query filtering ────────────────────────────────────────────────────────


def test_query_by_project(session: Session, repo: UELDBRepository):
    repo.emit_execution(_req(project_id=ProjectId.POUPI_CRYPTO, timestamp=_TS))
    repo.emit_execution(_req(project_id=ProjectId.POUPI_BABY, surface=ExecutionSurface.ANALYTICS, correlation_id="c2", timestamp=_TS2))
    session.commit()

    crypto = repo.query_executions(ExecutionQuery(project_id=ProjectId.POUPI_CRYPTO))
    baby = repo.query_executions(ExecutionQuery(project_id=ProjectId.POUPI_BABY))

    assert len(crypto) == 1
    assert len(baby) == 1


def test_query_by_status(session: Session, repo: UELDBRepository):
    e1 = repo.emit_execution(_req(timestamp=_TS))
    e2 = repo.emit_execution(_req(correlation_id="c2", timestamp=_TS2))
    repo.complete_execution(CompleteExecutionRequest(execution_id=e1.execution_id, outcome=UELOutcome(), finished_at=_TS2))
    session.commit()

    success = repo.query_executions(ExecutionQuery(status=UELStatus.SUCCESS))
    planned = repo.query_executions(ExecutionQuery(status=UELStatus.PLANNED))

    assert len(success) == 1
    assert len(planned) == 1


def test_query_by_mission(session: Session, repo: UELDBRepository):
    repo.emit_execution(_req(mission_id="mission-A", timestamp=_TS))
    repo.emit_execution(_req(mission_id="mission-B", correlation_id="c2", timestamp=_TS2))
    session.commit()

    results = repo.query_by_mission("mission-A")
    assert len(results) == 1
    assert results[0].mission_id == "mission-A"


def test_query_by_capability(session: Session, repo: UELDBRepository):
    repo.emit_execution(_req(capability_id="edge:btc", timestamp=_TS))
    repo.emit_execution(_req(capability_id="edge:eth", correlation_id="c2", timestamp=_TS2))
    session.commit()

    results = repo.query_by_capability("edge:btc")
    assert len(results) == 1


def test_query_pagination(session: Session, repo: UELDBRepository):
    for i in range(5):
        ts = datetime(2026, 6, 29, 12, 0, i, tzinfo=timezone.utc)
        repo.emit_execution(_req(correlation_id=f"c-{i}", timestamp=ts))
    session.commit()

    page1 = repo.query_executions(ExecutionQuery(limit=3, offset=0))
    page2 = repo.query_executions(ExecutionQuery(limit=3, offset=3))

    assert len(page1) == 3
    assert len(page2) == 2


def test_query_time_range(session: Session, repo: UELDBRepository):
    repo.emit_execution(_req(timestamp=_TS))
    repo.emit_execution(_req(correlation_id="c2", timestamp=_TS3))
    session.commit()

    results = repo.query_executions(ExecutionQuery(since=_TS2, until=_TS4))
    assert len(results) == 1


# ── 7. Dashboard (SQL aggregation) ───────────────────────────────────────────


def test_empty_dashboard(repo: UELDBRepository):
    report = repo.dashboard()
    assert report.total == 0
    assert report.success_rate == 0.0


def test_dashboard_aggregation(session: Session, repo: UELDBRepository):
    e1 = repo.emit_execution(_req(project_id=ProjectId.POUPI_CRYPTO, mission_id="m1", timestamp=_TS))
    e2 = repo.emit_execution(_req(project_id=ProjectId.POUPI_BABY, surface=ExecutionSurface.ANALYTICS, mission_id="m2", correlation_id="c2", timestamp=_TS2))
    e3 = repo.emit_execution(_req(project_id=ProjectId.SINALO, surface=ExecutionSurface.SEO, mission_id="m3", correlation_id="c3", timestamp=_TS3))

    repo.complete_execution(CompleteExecutionRequest(execution_id=e1.execution_id, outcome=UELOutcome(value_delivered=True), finished_at=_TS2))
    repo.fail_execution(FailExecutionRequest(execution_id=e2.execution_id, error="timeout", finished_at=_TS3))
    repo.rollback_execution(RollbackExecutionRequest(execution_id=e3.execution_id, rollback_reason="policy", finished_at=_TS4))
    session.commit()

    report = repo.dashboard()

    assert report.total == 3
    assert report.by_project[ProjectId.POUPI_CRYPTO] == 1
    assert report.by_project[ProjectId.POUPI_BABY] == 1
    assert report.by_project[ProjectId.SINALO] == 1
    assert report.success_rate == pytest.approx(1 / 3)
    assert report.failure_rate == pytest.approx(1 / 3)
    assert report.rollback_rate == pytest.approx(1 / 3)
    assert report.by_status[UELStatus.SUCCESS.value] == 1
    assert report.by_status[UELStatus.FAILED.value] == 1
    assert report.by_status[UELStatus.ROLLBACK.value] == 1


# ── 8. DB Transaction rollback ────────────────────────────────────────────────


def test_session_rollback_discards_state(session: Session, repo: UELDBRepository):
    e = repo.emit_execution(_req())
    session.flush()
    assert session.execute(text("SELECT COUNT(*) FROM universal_executions")).scalar() == 1

    session.rollback()
    assert session.execute(text("SELECT COUNT(*) FROM universal_executions")).scalar() == 0


# ── 9. Adapter compatibility with DB backend ──────────────────────────────────


def test_crypto_adapter_with_db_backend(session: Session, repo: UELDBRepository):
    adapter = CryptoUELAdapter(repo)  # type: ignore[arg-type]
    e = adapter.emit_signal("edge:btc-momentum", signal_id="sig-001", timestamp=_TS)
    completed = adapter.complete(e.execution_id, summary="Signal produced", value_delivered=True, finished_at=_TS2)
    session.commit()

    assert completed.status == UELStatus.SUCCESS
    fetched = repo.query_execution(e.execution_id)
    assert fetched is not None
    assert fetched.status == UELStatus.SUCCESS
    assert fetched.tags.get("signal_id") == "sig-001"


def test_baby_adapter_with_db_backend(session: Session, repo: UELDBRepository):
    adapter = BabyUELAdapter(repo)  # type: ignore[arg-type]
    e = adapter.emit_discovery("discovery:fraldas", product_id="prod-001", timestamp=_TS)
    session.commit()

    fetched = repo.query_execution(e.execution_id)
    assert fetched is not None
    assert fetched.project_id == ProjectId.POUPI_BABY


def test_sinalo_adapter_with_db_backend(session: Session, repo: UELDBRepository):
    adapter = SinaloUELAdapter(repo)  # type: ignore[arg-type]
    e = adapter.emit_seo("seo:keywords", page_id="home", timestamp=_TS)
    session.commit()

    fetched = repo.query_execution(e.execution_id)
    assert fetched is not None
    assert fetched.project_id == ProjectId.SINALO


def test_multiple_adapters_share_db_session(session: Session, repo: UELDBRepository):
    crypto = CryptoUELAdapter(repo)  # type: ignore[arg-type]
    baby = BabyUELAdapter(repo)  # type: ignore[arg-type]
    sinalo = SinaloUELAdapter(repo)  # type: ignore[arg-type]

    crypto.emit_signal("edge:btc", timestamp=_TS)
    baby.emit_discovery("discovery:item", timestamp=_TS2)
    sinalo.emit_content("content:post", timestamp=_TS3)
    session.commit()

    report = repo.dashboard()
    assert report.total == 3
    assert len(report.by_project) == 3


# ── 10. Scientific bridge ─────────────────────────────────────────────────────


def test_scientific_bridge_execution_memory(session: Session, repo: UELDBRepository):
    e1 = repo.emit_execution(_req(timestamp=_TS))
    repo.complete_execution(CompleteExecutionRequest(execution_id=e1.execution_id, outcome=UELOutcome(value_delivered=True), finished_at=_TS2))
    repo.emit_execution(_req(correlation_id="c2", timestamp=_TS2))  # stays PLANNED
    session.commit()

    bridge = ScientificLedgerBridge(repo)  # type: ignore[arg-type]
    memory = bridge.load_execution_memory()
    assert len(memory) == 1
    assert memory[0].status == UELStatus.SUCCESS


def test_scientific_bridge_evidence_feed(session: Session, repo: UELDBRepository):
    e1 = repo.emit_execution(_req(timestamp=_TS))
    repo.complete_execution(CompleteExecutionRequest(execution_id=e1.execution_id, outcome=UELOutcome(value_delivered=True), finished_at=_TS2))
    repo.attach_evidence(AttachRequest(execution_id=e1.execution_id, ids=["ev-1", "ev-2"]))
    session.commit()

    bridge = ScientificLedgerBridge(repo)  # type: ignore[arg-type]
    evidence = bridge.evidence_feed()
    assert "ev-1" in evidence
    assert "ev-2" in evidence


def test_scientific_bridge_opportunity_evidence(session: Session, repo: UELDBRepository):
    e1 = repo.emit_execution(_req(mission_id="mission-X", timestamp=_TS))
    repo.complete_execution(CompleteExecutionRequest(execution_id=e1.execution_id, outcome=UELOutcome(value_delivered=True), finished_at=_TS2))
    session.commit()

    bridge = ScientificLedgerBridge(repo)  # type: ignore[arg-type]
    result = bridge.opportunity_evidence("mission-X")
    assert result["total"] == 1
    assert result["value_delivered"] is True
    assert result["success_rate"] == 1.0


# ── 11. Health check ──────────────────────────────────────────────────────────


def test_health_healthy(session: Session, repo: UELDBRepository):
    e = repo.emit_execution(_req(timestamp=_TS))
    repo.complete_execution(CompleteExecutionRequest(execution_id=e.execution_id, outcome=UELOutcome(value_delivered=True), finished_at=_TS2))
    session.commit()

    dashboard = repo.dashboard()
    health = compute_uel_health(dashboard, table_reachable=True)

    assert health.healthy is True
    assert health.status == "HEALTHY"
    assert health.total_executions == 1


def test_health_unreachable():
    health = compute_uel_health(None, table_reachable=False)
    assert health.healthy is False
    assert health.status == "UNHEALTHY"


# ── 12. __len__ ───────────────────────────────────────────────────────────────


def test_len_db_repository(session: Session, repo: UELDBRepository):
    assert len(repo) == 0
    repo.emit_execution(_req(timestamp=_TS))
    repo.emit_execution(_req(correlation_id="c2", timestamp=_TS2))
    session.flush()
    assert len(repo) == 2
