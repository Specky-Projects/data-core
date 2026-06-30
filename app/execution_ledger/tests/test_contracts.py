from app.execution_ledger.contracts import (
    DecisionReadModel,
    ExecutionLedgerContract,
    ExecutionLedgerEntry,
    ExecutionLedgerRepository,
    LedgerEntryKind,
    LedgerEntryStatus,
    LedgerReadModel,
    LedgerRef,
    LedgerReplay,
    LedgerReplayEntry,
    LedgerTimeline,
    LedgerTimelineEntry,
    OutcomeReadModel,
    TradeReadModel,
)


def _entry(kind: LedgerEntryKind = LedgerEntryKind.DECISION) -> ExecutionLedgerEntry:
    return ExecutionLedgerEntry(
        entry_id="entry-001",
        lineage_id="lin-001",
        kind=kind,
        status=LedgerEntryStatus.OPEN,
        domain="crypto",
        recorded_at="2026-06-30T00:00:00Z",
        refs=(LedgerRef(kind=kind, ref_id="ref-001"),),
    )


def test_entry_validates() -> None:
    assert _entry().validate() == []


def test_entry_missing_fields() -> None:
    entry = ExecutionLedgerEntry(
        entry_id="",
        lineage_id="",
        kind=LedgerEntryKind.TRADE,
        status=LedgerEntryStatus.OPEN,
        domain="",
        recorded_at="",
        refs=(),
    )
    errors = entry.validate()
    assert "entry_id is required" in errors
    assert "lineage_id is required" in errors
    assert "domain is required" in errors


def test_ledger_contract_entries_by_kind() -> None:
    decision = _entry(LedgerEntryKind.DECISION)
    trade = _entry(LedgerEntryKind.TRADE)
    trade_dup = ExecutionLedgerEntry(
        entry_id="entry-002",
        lineage_id="lin-001",
        kind=LedgerEntryKind.TRADE,
        status=LedgerEntryStatus.CLOSED,
        domain="crypto",
        recorded_at="2026-06-30T00:00:00Z",
        refs=(),
    )
    ledger = ExecutionLedgerContract(
        ledger_id="ledger-001",
        domain="crypto",
        from_date="2026-01-01",
        to_date="2026-06-30",
        entries=(decision, trade, trade_dup),
    )
    assert len(ledger.entries_by_kind(LedgerEntryKind.TRADE)) == 2
    assert len(ledger.entries_by_kind(LedgerEntryKind.DECISION)) == 1
    assert ledger.validate() == []


def test_ledger_contract_entries_for_lineage() -> None:
    e1 = _entry()
    e2 = ExecutionLedgerEntry(
        entry_id="entry-002",
        lineage_id="lin-999",
        kind=LedgerEntryKind.OUTCOME,
        status=LedgerEntryStatus.CLOSED,
        domain="crypto",
        recorded_at="2026-06-30T00:00:00Z",
        refs=(),
    )
    ledger = ExecutionLedgerContract(
        ledger_id="l1",
        domain="crypto",
        from_date="2026-01-01",
        to_date="2026-06-30",
        entries=(e1, e2),
    )
    assert ledger.entries_for_lineage("lin-001") == (e1,)
    assert ledger.entries_for_lineage("lin-999") == (e2,)


def test_read_model_is_complete_only_with_decisions_and_outcomes() -> None:
    decision = DecisionReadModel(
        decision_id="d1",
        lineage_id="lin-001",
        stage="SIGNAL",
        action="APPROVE",
        reason_code="SIGNAL_QUALIFIED",
        confidence=0.8,
        decided_at="2026-06-30T00:00:00Z",
        domain="crypto",
        strategy="specky",
    )
    outcome = OutcomeReadModel(
        outcome_id="o1",
        lineage_id="lin-001",
        trade_id="t1",
        result="WIN",
        realized_pnl=10.0,
        edge_actual=0.05,
        edge_expected=0.04,
        recorded_at="2026-06-30T01:00:00Z",
        domain="crypto",
    )
    model = LedgerReadModel(
        lineage_id="lin-001",
        domain="crypto",
        decisions=(decision,),
        trades=(),
        outcomes=(outcome,),
        evidence_refs=(),
        learning_refs=(),
        created_at="2026-06-30T00:00:00Z",
    )
    assert model.is_complete()


def test_read_model_incomplete_without_outcomes() -> None:
    decision = DecisionReadModel(
        decision_id="d1",
        lineage_id="lin-001",
        stage="SIGNAL",
        action="REJECT",
        reason_code="LOW_CONFIDENCE",
        confidence=0.3,
        decided_at="t",
        domain="crypto",
        strategy=None,
    )
    model = LedgerReadModel(
        lineage_id="lin-001",
        domain="crypto",
        decisions=(decision,),
        trades=(),
        outcomes=(),
        evidence_refs=(),
        learning_refs=(),
        created_at="t",
    )
    assert not model.is_complete()


def test_timeline_for_lineage() -> None:
    e1 = LedgerTimelineEntry(
        timestamp="2026-06-30T00:00:00Z",
        kind=LedgerEntryKind.DECISION,
        entry_id="e1",
        lineage_id="lin-001",
        summary="decision approved",
    )
    e2 = LedgerTimelineEntry(
        timestamp="2026-06-30T01:00:00Z",
        kind=LedgerEntryKind.OUTCOME,
        entry_id="e2",
        lineage_id="lin-002",
        summary="outcome recorded",
    )
    tl = LedgerTimeline(
        timeline_id="tl-001",
        domain="crypto",
        from_date="2026-01-01",
        to_date="2026-06-30",
        entries=(e1, e2),
    )
    assert tl.for_lineage("lin-001") == (e1,)
    assert tl.validate() == []


def test_replay_has_divergence() -> None:
    r1 = LedgerReplayEntry(original_entry_id="e1", replayed_at="t", deterministic=True, divergence_detected=False)
    r2 = LedgerReplayEntry(original_entry_id="e2", replayed_at="t", deterministic=False, divergence_detected=True, divergence_reason="confidence delta")
    replay = LedgerReplay(replay_id="r1", ledger_id="l1", replayed_entries=(r1, r2), replay_initiated_at="t")
    assert replay.has_divergence()
    assert replay.validate() == []


def test_replay_empty_entries_invalid() -> None:
    replay = LedgerReplay(replay_id="r1", ledger_id="l1", replayed_entries=(), replay_initiated_at="t")
    errors = replay.validate()
    assert any("replayed_entries" in e for e in errors)


def test_repository_is_abstract() -> None:
    repo = ExecutionLedgerRepository()
    try:
        repo.append(_entry())
        assert False
    except NotImplementedError:
        pass
