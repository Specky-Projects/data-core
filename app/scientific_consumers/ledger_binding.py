"""Execution Ledger binding — records a consumer decision's lifecycle as
canonical, append-only ledger entries (DECISION, COMMITTEE, EVIDENCE, PREVIEW
and, when present, OUTCOME/REPLAY/LEARNING).

Read-only projection: it appends observational records; it never issues orders.
"""
from __future__ import annotations

from app.execution_ledger.contracts import (
    ExecutionLedgerContract,
    ExecutionLedgerEntry,
    LedgerEntryKind,
    LedgerEntryStatus,
    LedgerRef,
)
from app.scientific_consumers.facts import DecisionFacts
from app.scientific_identity.contract import stable_hash


def _entry(facts: DecisionFacts, kind: LedgerEntryKind, status: LedgerEntryStatus,
           payload: dict) -> ExecutionLedgerEntry:
    return ExecutionLedgerEntry(
        entry_id=stable_hash({"lineage": facts.lineage_id, "kind": kind.value}),
        lineage_id=facts.lineage_id, kind=kind, status=status, domain=facts.domain,
        recorded_at=facts.decided_at,
        refs=(LedgerRef(kind=kind, ref_id=facts.decision_id,
                        ref_hash=stable_hash(payload)),),
        payload_hash=stable_hash(payload),
        metadata={"consumer": facts.consumer, "advisory_only": True},
    )


def build_ledger_entries(facts: DecisionFacts) -> tuple[ExecutionLedgerEntry, ...]:
    entries = [
        _entry(facts, LedgerEntryKind.EVIDENCE, LedgerEntryStatus.CLOSED,
               {"shadow_signal": facts.decision_id,
                "sources": sorted(e.source_name for e in facts.evidence)}),
        _entry(facts, LedgerEntryKind.COMMITTEE, LedgerEntryStatus.CLOSED,
               {"verdict": facts.committee_verdict, "confidence": facts.committee_confidence}),
        _entry(facts, LedgerEntryKind.DECISION,
               LedgerEntryStatus.CLOSED if facts.outcome else LedgerEntryStatus.OPEN,
               {"verdict": facts.verdict, "action": facts.action, "confidence": facts.confidence}),
        _entry(facts, LedgerEntryKind.PREVIEW, LedgerEntryStatus.CLOSED,
               {"action": facts.action, "simulation_only": facts.simulation_only,
                "requires_human_review": facts.requires_human_review,
                "shadow_execution_attempt": True}),
        _entry(facts, LedgerEntryKind.REPLAY, LedgerEntryStatus.CLOSED,
               {"decision_id": facts.decision_id, "lineage_id": facts.lineage_id,
                "shadow_replay_reference": True}),
    ]
    if facts.outcome is not None:
        entries.append(_entry(facts, LedgerEntryKind.OUTCOME, LedgerEntryStatus.CLOSED,
                              {"kind": facts.outcome.kind,
                               "realized": facts.outcome.realized_value,
                               "expected": facts.outcome.expected_value}))
        entries.append(_entry(facts, LedgerEntryKind.LEARNING, LedgerEntryStatus.CLOSED,
                              {"outcome_kind": facts.outcome.kind, "advisory_only": True,
                               "shadow_learning_reference": True}))
    return tuple(entries)


def build_ledger(facts: DecisionFacts) -> ExecutionLedgerContract:
    entries = build_ledger_entries(facts)
    day = (facts.decided_at or "")[:10]
    return ExecutionLedgerContract(
        ledger_id=stable_hash({"lineage": facts.lineage_id, "kind": "ledger"}),
        domain=facts.domain, from_date=day, to_date=day, entries=entries,
    )
