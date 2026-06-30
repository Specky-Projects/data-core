"""Business OS 5.0 — Universal Execution Log tests.

Covers:
  - Canonical contract completeness
  - Deterministic execution ID generation
  - Full lifecycle: emit → running → complete / fail / rollback
  - Evidence / knowledge / learning attachment
  - Parent-child lineage
  - Retry and replay relations
  - Dashboard aggregation
  - Cross-project isolation and unification
  - All project adapters (Crypto, Baby, Sinalo, BusinessOS)
  - ExecutionQuery filtering
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.universal_execution_log import (
    AttachRequest,
    BabyUELAdapter,
    BusinessOSUELAdapter,
    CompleteExecutionRequest,
    CryptoUELAdapter,
    EmitExecutionRequest,
    ExecutionQuery,
    ExecutionRelation,
    ExecutionSurface,
    ExecutionType,
    FailExecutionRequest,
    ProjectId,
    RollbackExecutionRequest,
    SinaloUELAdapter,
    UEL_SCHEMA_VERSION,
    UEL_VERSION,
    UELAdapter,
    UELDecision,
    UELMetrics,
    UELOutcome,
    UELRepository,
    UELStatus,
    UniversalExecution,
    build_execution_id,
)

_TS = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)
_TS2 = datetime(2026, 6, 29, 12, 0, 1, tzinfo=timezone.utc)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _repo() -> UELRepository:
    return UELRepository()


def _emit_req(
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


# ── 1. Contract completeness ───────────────────────────────────────────────────


def test_execution_id_is_deterministic():
    id1 = build_execution_id("crypto", "edge:btc", "trading", "corr-1", _TS)
    id2 = build_execution_id("crypto", "edge:btc", "trading", "corr-1", _TS)
    assert id1 == id2
    assert id1.startswith("uel:")


def test_execution_id_differs_on_different_inputs():
    id1 = build_execution_id("crypto", "edge:btc", "trading", "corr-1", _TS)
    id2 = build_execution_id("crypto", "edge:eth", "trading", "corr-1", _TS)
    assert id1 != id2


def test_emit_returns_canonical_execution():
    repo = _repo()
    execution = repo.emit_execution(_emit_req())

    assert isinstance(execution, UniversalExecution)
    assert execution.execution_id.startswith("uel:")
    assert execution.schema_version == UEL_SCHEMA_VERSION
    assert execution.uel_version == UEL_VERSION
    assert execution.status == UELStatus.PLANNED
    assert execution.project_id == ProjectId.POUPI_CRYPTO
    assert execution.capability_id == "edge:btc-momentum"
    assert execution.mission_id == "mission-001"
    assert execution.lineage.mission_id == "mission-001"
    assert execution.lineage.lineage_hash != ""


def test_emit_populates_all_canonical_fields():
    repo = _repo()
    req = EmitExecutionRequest(
        project_id=ProjectId.POUPI_BABY,
        capability_id="discovery:product",
        execution_surface=ExecutionSurface.ANALYTICS,
        execution_type=ExecutionType.DISCOVERY,
        actor="baby-engine",
        executor="scraper-v2",
        planner="planner-v1",
        reviewer="committee",
        mission_id="mission-baby",
        portfolio_id="portfolio-x",
        correlation_id="corr-baby",
        parent_execution_id="parent-001",
        execution_plan_id="plan-001",
        decision=UELDecision(decision_id="dec-001", confidence=0.9),
        tags={"env": "production"},
        timestamp=_TS,
    )
    e = repo.emit_execution(req)

    assert e.project_id == ProjectId.POUPI_BABY
    assert e.executor == "scraper-v2"
    assert e.planner == "planner-v1"
    assert e.reviewer == "committee"
    assert e.portfolio_id == "portfolio-x"
    assert e.parent_execution_id == "parent-001"
    assert e.execution_plan_id == "plan-001"
    assert e.decision.decision_id == "dec-001"
    assert e.decision.confidence == 0.9
    assert e.tags == {"env": "production"}
    assert e.lineage.parent_execution_id == "parent-001"


# ── 2. Lifecycle transitions ───────────────────────────────────────────────────


def test_complete_execution_sets_success():
    repo = _repo()
    e = repo.emit_execution(_emit_req(timestamp=_TS))

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

    assert completed.status == UELStatus.SUCCESS
    assert completed.outcome.summary == "Signal produced"
    assert completed.outcome.value_delivered is True
    assert completed.outcome.artifacts == ["sig-001"]
    assert completed.metrics.latency_ms == 42.0
    assert completed.finished_at == _TS2
    assert completed.duration_ms == pytest.approx(1000.0)


def test_fail_execution_sets_failed():
    repo = _repo()
    e = repo.emit_execution(_emit_req(timestamp=_TS))

    failed = repo.fail_execution(
        FailExecutionRequest(
            execution_id=e.execution_id,
            error="Timeout connecting to exchange",
            errors=["Connection refused"],
            finished_at=_TS2,
        )
    )

    assert failed.status == UELStatus.FAILED
    assert "Timeout connecting to exchange" in failed.outcome.errors
    assert failed.outcome.value_delivered is False


def test_rollback_execution_sets_rollback():
    repo = _repo()
    e = repo.emit_execution(_emit_req(timestamp=_TS))

    rolled = repo.rollback_execution(
        RollbackExecutionRequest(
            execution_id=e.execution_id,
            rollback_reason="Kill switch triggered",
            rollback_target_id="checkpoint-001",
            finished_at=_TS2,
        )
    )

    assert rolled.status == UELStatus.ROLLBACK
    assert rolled.relation == ExecutionRelation.ROLLBACK
    assert rolled.outcome.rollback_available is True
    assert "checkpoint-001" in rolled.outcome.artifacts


def test_unknown_execution_id_raises():
    repo = _repo()
    with pytest.raises(KeyError):
        repo.complete_execution(
            CompleteExecutionRequest(
                execution_id="uel:nonexistent",
                outcome=UELOutcome(),
                finished_at=_TS,
            )
        )


# ── 3. Evidence / knowledge / learning attachment ──────────────────────────────


def test_attach_evidence():
    repo = _repo()
    e = repo.emit_execution(_emit_req())
    updated = repo.attach_evidence(AttachRequest(execution_id=e.execution_id, ids=["ev-1", "ev-2"]))
    assert "ev-1" in updated.evidence_ids
    assert "ev-2" in updated.evidence_ids


def test_attach_knowledge():
    repo = _repo()
    e = repo.emit_execution(_emit_req())
    updated = repo.attach_knowledge(AttachRequest(execution_id=e.execution_id, ids=["kn-1"]))
    assert "kn-1" in updated.knowledge_ids


def test_attach_learning():
    repo = _repo()
    e = repo.emit_execution(_emit_req())
    updated = repo.attach_learning(AttachRequest(execution_id=e.execution_id, ids=["lr-1"]))
    assert "lr-1" in updated.learning_ids


def test_attach_deduplicates():
    repo = _repo()
    e = repo.emit_execution(_emit_req())
    repo.attach_evidence(AttachRequest(execution_id=e.execution_id, ids=["ev-1"]))
    updated = repo.attach_evidence(AttachRequest(execution_id=e.execution_id, ids=["ev-1", "ev-2"]))
    assert updated.evidence_ids.count("ev-1") == 1
    assert "ev-2" in updated.evidence_ids


# ── 4. Parent-child lineage ────────────────────────────────────────────────────


def test_parent_child_lineage():
    repo = _repo()
    parent = repo.emit_execution(_emit_req(correlation_id="corr-parent", timestamp=_TS))

    child_req = EmitExecutionRequest(
        project_id=ProjectId.POUPI_CRYPTO,
        capability_id="edge:btc-momentum",
        execution_surface=ExecutionSurface.TRADING,
        execution_type=ExecutionType.TRADE,
        actor="executor",
        parent_execution_id=parent.execution_id,
        relation=ExecutionRelation.CHILD,
        timestamp=_TS2,
    )
    child = repo.emit_execution(child_req)

    assert child.parent_execution_id == parent.execution_id
    assert child.relation == ExecutionRelation.CHILD

    children = repo.query_children(parent.execution_id)
    assert len(children) == 1
    assert children[0].execution_id == child.execution_id


# ── 5. Retry / replay relations ───────────────────────────────────────────────


def test_retry_relation():
    repo = _repo()
    original = repo.emit_execution(_emit_req(timestamp=_TS))
    repo.fail_execution(
        FailExecutionRequest(execution_id=original.execution_id, error="timeout", finished_at=_TS2)
    )

    retry_req = EmitExecutionRequest(
        project_id=ProjectId.POUPI_CRYPTO,
        capability_id="edge:btc-momentum",
        execution_surface=ExecutionSurface.TRADING,
        execution_type=ExecutionType.SIGNAL,
        actor="crypto-engine",
        parent_execution_id=original.execution_id,
        relation=ExecutionRelation.RETRY,
        timestamp=_TS2,
    )
    retry = repo.emit_execution(retry_req)

    assert retry.relation == ExecutionRelation.RETRY
    assert retry.parent_execution_id == original.execution_id


# ── 6. Query filtering ────────────────────────────────────────────────────────


def test_query_by_project():
    repo = _repo()
    repo.emit_execution(_emit_req(project_id=ProjectId.POUPI_CRYPTO, timestamp=_TS))
    repo.emit_execution(_emit_req(project_id=ProjectId.POUPI_BABY, surface=ExecutionSurface.ANALYTICS, timestamp=_TS2))

    crypto_results = repo.query_executions(ExecutionQuery(project_id=ProjectId.POUPI_CRYPTO))
    baby_results = repo.query_executions(ExecutionQuery(project_id=ProjectId.POUPI_BABY))

    assert len(crypto_results) == 1
    assert len(baby_results) == 1


def test_query_by_status():
    repo = _repo()
    e1 = repo.emit_execution(_emit_req(timestamp=_TS))
    e2 = repo.emit_execution(_emit_req(correlation_id="corr-002", timestamp=_TS2))
    repo.complete_execution(CompleteExecutionRequest(execution_id=e1.execution_id, outcome=UELOutcome(), finished_at=_TS2))

    success = repo.query_executions(ExecutionQuery(status=UELStatus.SUCCESS))
    planned = repo.query_executions(ExecutionQuery(status=UELStatus.PLANNED))

    assert len(success) == 1
    assert len(planned) == 1


def test_query_by_mission():
    repo = _repo()
    repo.emit_execution(_emit_req(mission_id="mission-A", timestamp=_TS))
    repo.emit_execution(_emit_req(mission_id="mission-B", correlation_id="corr-B", timestamp=_TS2))

    results = repo.query_by_mission("mission-A")
    assert len(results) == 1
    assert results[0].mission_id == "mission-A"


def test_query_by_capability():
    repo = _repo()
    repo.emit_execution(_emit_req(capability_id="edge:btc", timestamp=_TS))
    repo.emit_execution(_emit_req(capability_id="edge:eth", correlation_id="c2", timestamp=_TS2))

    results = repo.query_by_capability("edge:btc")
    assert len(results) == 1


def test_query_pagination():
    repo = _repo()
    for i in range(5):
        ts = datetime(2026, 6, 29, 12, 0, i, tzinfo=timezone.utc)
        repo.emit_execution(_emit_req(correlation_id=f"corr-{i}", timestamp=ts))

    page1 = repo.query_executions(ExecutionQuery(limit=3, offset=0))
    page2 = repo.query_executions(ExecutionQuery(limit=3, offset=3))
    assert len(page1) == 3
    assert len(page2) == 2


# ── 7. Dashboard ──────────────────────────────────────────────────────────────


def test_empty_dashboard():
    repo = _repo()
    report = repo.dashboard()
    assert report.total == 0
    assert report.success_rate == 0.0


def test_dashboard_aggregation():
    repo = _repo()

    e1 = repo.emit_execution(_emit_req(project_id=ProjectId.POUPI_CRYPTO, mission_id="m1", timestamp=_TS))
    e2 = repo.emit_execution(_emit_req(project_id=ProjectId.POUPI_BABY, surface=ExecutionSurface.ANALYTICS, mission_id="m2", correlation_id="c2", timestamp=_TS2))
    ts3 = datetime(2026, 6, 29, 12, 0, 2, tzinfo=timezone.utc)
    e3 = repo.emit_execution(_emit_req(project_id=ProjectId.SINALO, surface=ExecutionSurface.SEO, mission_id="m3", correlation_id="c3", timestamp=ts3))

    repo.complete_execution(CompleteExecutionRequest(execution_id=e1.execution_id, outcome=UELOutcome(value_delivered=True), finished_at=_TS2))
    repo.fail_execution(FailExecutionRequest(execution_id=e2.execution_id, error="timeout", finished_at=_TS2))
    repo.rollback_execution(RollbackExecutionRequest(execution_id=e3.execution_id, rollback_reason="policy", finished_at=ts3))

    repo.attach_evidence(AttachRequest(execution_id=e1.execution_id, ids=["ev-1", "ev-2"]))
    repo.attach_learning(AttachRequest(execution_id=e1.execution_id, ids=["lr-1"]))

    report = repo.dashboard()

    assert report.total == 3
    assert report.by_project[ProjectId.POUPI_CRYPTO] == 1
    assert report.by_project[ProjectId.POUPI_BABY] == 1
    assert report.by_project[ProjectId.SINALO] == 1
    assert report.success_rate == pytest.approx(1 / 3)
    assert report.failure_rate == pytest.approx(1 / 3)
    assert report.rollback_rate == pytest.approx(1 / 3)
    assert report.total_evidence_attached == 2
    assert report.total_learnings_attached == 1
    assert report.by_status[UELStatus.SUCCESS] == 1
    assert report.by_status[UELStatus.FAILED] == 1
    assert report.by_status[UELStatus.ROLLBACK] == 1


# ── 8. Project adapters ───────────────────────────────────────────────────────


def test_crypto_adapter_emit_signal():
    repo = _repo()
    adapter = CryptoUELAdapter(repo)
    e = adapter.emit_signal("edge:btc-momentum", signal_id="sig-001", timestamp=_TS)

    assert e.project_id == ProjectId.POUPI_CRYPTO
    assert e.execution_surface == ExecutionSurface.TRADING
    assert e.execution_type == ExecutionType.SIGNAL
    assert e.tags.get("signal_id") == "sig-001"


def test_crypto_adapter_full_lifecycle():
    repo = _repo()
    adapter = CryptoUELAdapter(repo)

    e = adapter.emit_trade("executor:btc-buy", trade_id="trade-001", timestamp=_TS)
    completed = adapter.complete(
        e.execution_id,
        summary="BTC bought at 42000",
        value_delivered=True,
        latency_ms=55.0,
        finished_at=_TS2,
    )

    assert completed.status == UELStatus.SUCCESS
    assert completed.outcome.value_delivered is True
    assert completed.metrics.latency_ms == 55.0


def test_baby_adapter_emit_discovery():
    repo = _repo()
    adapter = BabyUELAdapter(repo)
    e = adapter.emit_discovery("discovery:fraldas", product_id="prod-123", timestamp=_TS)

    assert e.project_id == ProjectId.POUPI_BABY
    assert e.execution_type == ExecutionType.DISCOVERY
    assert e.tags.get("product_id") == "prod-123"


def test_baby_adapter_emit_alert():
    repo = _repo()
    adapter = BabyUELAdapter(repo)
    e = adapter.emit_alert("alert:price-drop", alert_id="alert-001", timestamp=_TS)

    assert e.execution_surface == ExecutionSurface.WORKFLOW
    assert e.execution_type == ExecutionType.ALERT


def test_sinalo_adapter_emit_content():
    repo = _repo()
    adapter = SinaloUELAdapter(repo)
    e = adapter.emit_content("content:article-seo", content_id="art-001", timestamp=_TS)

    assert e.project_id == ProjectId.SINALO
    assert e.execution_surface == ExecutionSurface.CONTENT
    assert e.execution_type == ExecutionType.PUBLISH


def test_sinalo_adapter_emit_seo():
    repo = _repo()
    adapter = SinaloUELAdapter(repo)
    e = adapter.emit_seo("seo:keyword-rank", page_id="page-home", timestamp=_TS)

    assert e.execution_surface == ExecutionSurface.SEO
    assert e.execution_type == ExecutionType.ANALYZE


def test_business_os_adapter():
    repo = _repo()
    adapter = BusinessOSUELAdapter(repo)
    e = adapter.emit("orchestrator:capability-evolution", actor="kernel", timestamp=_TS)

    assert e.project_id == ProjectId.BUSINESS_OS
    assert e.execution_surface == ExecutionSurface.AUTONOMOUS_DECISION


def test_adapters_share_repository():
    repo = _repo()
    crypto = CryptoUELAdapter(repo)
    baby = BabyUELAdapter(repo)
    sinalo = SinaloUELAdapter(repo)

    crypto.emit_signal("edge:btc", timestamp=_TS)
    baby.emit_discovery("discovery:item", timestamp=_TS2)
    ts3 = datetime(2026, 6, 29, 12, 0, 2, tzinfo=timezone.utc)
    sinalo.emit_content("content:post", timestamp=ts3)

    assert len(repo) == 3
    report = repo.dashboard()
    assert report.total == 3
    assert len(report.by_project) == 3


# ── 9. Attach via adapter ─────────────────────────────────────────────────────


def test_attach_evidence_via_adapter():
    repo = _repo()
    adapter = CryptoUELAdapter(repo)
    e = adapter.emit_signal("edge:btc", timestamp=_TS)

    updated = adapter.attach_evidence(e.execution_id, ["ev-001", "ev-002"])
    assert "ev-001" in updated.evidence_ids


def test_attach_learning_via_adapter():
    repo = _repo()
    adapter = CryptoUELAdapter(repo)
    e = adapter.emit_signal("edge:btc", timestamp=_TS)

    updated = adapter.attach_learning(e.execution_id, ["lr-001"])
    assert "lr-001" in updated.learning_ids


# ── 10. Cross-project unification ────────────────────────────────────────────


def test_all_executions_share_single_canonical_schema():
    repo = _repo()
    adapters = [
        CryptoUELAdapter(repo),
        BabyUELAdapter(repo),
        SinaloUELAdapter(repo),
        BusinessOSUELAdapter(repo),
    ]
    timestamps = [
        datetime(2026, 6, 29, 12, 0, i, tzinfo=timezone.utc) for i in range(4)
    ]
    for i, adapter in enumerate(adapters):
        adapter.emit("capability:unified", timestamp=timestamps[i])

    all_execs = repo.query_executions(ExecutionQuery(limit=10))
    assert len(all_execs) == 4

    for e in all_execs:
        assert isinstance(e, UniversalExecution)
        assert e.schema_version == UEL_SCHEMA_VERSION
        assert e.uel_version == UEL_VERSION
        assert e.execution_id.startswith("uel:")
        assert e.lineage.lineage_hash != ""
