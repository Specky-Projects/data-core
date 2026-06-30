"""
TEAM D — Execution Ledger
Scientific ledger consolidating Decision, Trade, Preview, Committee, Risk,
Evidence, Replay, Outcome and Learning into a single read model.
Never alters existing tables.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


LEDGER_CONTRACT_VERSION = "execution-ledger-v1"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LedgerEntryKind(StrEnum):
    DECISION = "DECISION"
    TRADE = "TRADE"
    PREVIEW = "PREVIEW"
    COMMITTEE = "COMMITTEE"
    RISK = "RISK"
    EVIDENCE = "EVIDENCE"
    REPLAY = "REPLAY"
    OUTCOME = "OUTCOME"
    LEARNING = "LEARNING"


class LedgerEntryStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    REPLAYED = "REPLAYED"
    INVALIDATED = "INVALIDATED"


# ---------------------------------------------------------------------------
# Ledger entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LedgerRef:
    kind: LedgerEntryKind
    ref_id: str
    ref_hash: str | None = None


@dataclass(frozen=True)
class ExecutionLedgerEntry:
    entry_id: str
    lineage_id: str
    kind: LedgerEntryKind
    status: LedgerEntryStatus
    domain: str
    recorded_at: str
    refs: tuple[LedgerRef, ...]
    payload_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.entry_id:
            errors.append("entry_id is required")
        if not self.lineage_id:
            errors.append("lineage_id is required")
        if not self.domain:
            errors.append("domain is required")
        if not self.recorded_at:
            errors.append("recorded_at is required")
        return errors


# ---------------------------------------------------------------------------
# Ledger contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionLedgerContract:
    """Root contract representing the complete scientific ledger."""

    ledger_id: str
    domain: str
    from_date: str
    to_date: str
    entries: tuple[ExecutionLedgerEntry, ...]
    contract_version: str = LEDGER_CONTRACT_VERSION

    def entries_by_kind(self, kind: LedgerEntryKind) -> tuple[ExecutionLedgerEntry, ...]:
        return tuple(e for e in self.entries if e.kind == kind)

    def entries_for_lineage(self, lineage_id: str) -> tuple[ExecutionLedgerEntry, ...]:
        return tuple(e for e in self.entries if e.lineage_id == lineage_id)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.ledger_id:
            errors.append("ledger_id is required")
        if not self.domain:
            errors.append("domain is required")
        for entry in self.entries:
            errors.extend(entry.validate())
        return errors


# ---------------------------------------------------------------------------
# Read models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionReadModel:
    decision_id: str
    lineage_id: str
    stage: str
    action: str
    reason_code: str
    confidence: float | None
    decided_at: str
    domain: str
    strategy: str | None


@dataclass(frozen=True)
class TradeReadModel:
    trade_id: str
    lineage_id: str
    symbol: str
    side: str
    size: float | None
    entry_price: float | None
    exit_price: float | None
    pnl: float | None
    opened_at: str
    closed_at: str | None
    domain: str
    strategy: str | None


@dataclass(frozen=True)
class OutcomeReadModel:
    outcome_id: str
    lineage_id: str
    trade_id: str | None
    result: str
    realized_pnl: float | None
    edge_actual: float | None
    edge_expected: float | None
    recorded_at: str
    domain: str


@dataclass(frozen=True)
class LedgerReadModel:
    """Unified view across all entry kinds for one lineage."""

    lineage_id: str
    domain: str
    decisions: tuple[DecisionReadModel, ...]
    trades: tuple[TradeReadModel, ...]
    outcomes: tuple[OutcomeReadModel, ...]
    evidence_refs: tuple[str, ...]
    learning_refs: tuple[str, ...]
    created_at: str

    def is_complete(self) -> bool:
        return bool(self.decisions and self.outcomes)


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LedgerTimelineEntry:
    timestamp: str
    kind: LedgerEntryKind
    entry_id: str
    lineage_id: str
    summary: str


@dataclass(frozen=True)
class LedgerTimeline:
    timeline_id: str
    domain: str
    from_date: str
    to_date: str
    entries: tuple[LedgerTimelineEntry, ...]

    def for_lineage(self, lineage_id: str) -> tuple[LedgerTimelineEntry, ...]:
        return tuple(e for e in self.entries if e.lineage_id == lineage_id)

    def validate(self) -> list[str]:
        if not self.timeline_id:
            return ["timeline_id is required"]
        return []


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LedgerReplayEntry:
    original_entry_id: str
    replayed_at: str
    deterministic: bool
    divergence_detected: bool
    divergence_reason: str | None = None


@dataclass(frozen=True)
class LedgerReplay:
    replay_id: str
    ledger_id: str
    replayed_entries: tuple[LedgerReplayEntry, ...]
    replay_initiated_at: str
    contract_version: str = LEDGER_CONTRACT_VERSION

    def has_divergence(self) -> bool:
        return any(e.divergence_detected for e in self.replayed_entries)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.replay_id:
            errors.append("replay_id is required")
        if not self.ledger_id:
            errors.append("ledger_id is required")
        if not self.replayed_entries:
            errors.append("replayed_entries must not be empty")
        return errors


# ---------------------------------------------------------------------------
# Repository interface
# ---------------------------------------------------------------------------


class ExecutionLedgerRepository:
    """Abstract read-only ledger repository."""

    def append(self, entry: ExecutionLedgerEntry) -> None:
        raise NotImplementedError

    def load_lineage(self, lineage_id: str) -> LedgerReadModel | None:
        raise NotImplementedError

    def timeline(self, domain: str, from_date: str, to_date: str) -> LedgerTimeline:
        raise NotImplementedError

    def full_ledger(self, domain: str, from_date: str, to_date: str) -> ExecutionLedgerContract:
        raise NotImplementedError

    def replay(self, ledger_id: str) -> LedgerReplay:
        raise NotImplementedError
