"""
TEAM C — Universal Learning
Passive scientific learning layer. Never alters decisions or executes actions.
All outputs are read-only snapshots derived from existing operational data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


LEARNING_CONTRACT_VERSION = "universal-learning-v1"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LearningSource(str, Enum):
    MIRROR = "MIRROR"
    RESEARCH = "RESEARCH"
    OUTCOME = "OUTCOME"
    REPLAY = "REPLAY"
    STATISTICS = "STATISTICS"
    EVIDENCE = "EVIDENCE"


class LearningSignalKind(str, Enum):
    EDGE_CONFIRMATION = "EDGE_CONFIRMATION"
    EDGE_REJECTION = "EDGE_REJECTION"
    CONFIDENCE_DRIFT = "CONFIDENCE_DRIFT"
    REGIME_SHIFT = "REGIME_SHIFT"
    FEATURE_IMPORTANCE_CHANGE = "FEATURE_IMPORTANCE_CHANGE"
    OUTCOME_ANOMALY = "OUTCOME_ANOMALY"
    REPLAY_DIVERGENCE = "REPLAY_DIVERGENCE"


class LearningMaturity(str, Enum):
    BOOTSTRAP = "BOOTSTRAP"
    EMERGING = "EMERGING"
    STABLE = "STABLE"
    SATURATED = "SATURATED"


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LearningEvidence:
    evidence_id: str
    source: LearningSource
    source_ref: str
    captured_at: str
    payload_hash: str
    quality_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.evidence_id:
            errors.append("evidence_id is required")
        if not self.source_ref:
            errors.append("source_ref is required")
        if self.quality_score is not None and not 0.0 <= self.quality_score <= 1.0:
            errors.append("quality_score must be between 0 and 1")
        return errors


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LearningSnapshot:
    """Point-in-time capture of the learning state for one domain/strategy."""

    snapshot_id: str
    domain: str
    strategy: str | None
    captured_at: str
    maturity: LearningMaturity
    sample_size: int
    evidence_refs: tuple[str, ...]
    metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    contract_version: str = LEARNING_CONTRACT_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.snapshot_id:
            errors.append("snapshot_id is required")
        if not self.domain:
            errors.append("domain is required")
        if self.sample_size < 0:
            errors.append("sample_size must be >= 0")
        return errors


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LearningSignal:
    """Passive learning signal — read-only, must never trigger execution."""

    signal_id: str
    kind: LearningSignalKind
    domain: str
    strategy: str | None
    detected_at: str
    snapshot_ref: str
    magnitude: float
    direction: str
    description: str
    evidence_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    ADVISORY_ONLY: bool = True

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.signal_id:
            errors.append("signal_id is required")
        if not 0.0 <= self.magnitude <= 1.0:
            errors.append("magnitude must be between 0 and 1")
        return errors


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LearningTimelineEntry:
    entry_id: str
    snapshot_ref: str
    recorded_at: str
    maturity: LearningMaturity
    delta_metrics: dict[str, float] = field(default_factory=dict)
    signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class LearningTimeline:
    timeline_id: str
    domain: str
    strategy: str | None
    entries: tuple[LearningTimelineEntry, ...]
    from_date: str
    to_date: str

    def latest_entry(self) -> LearningTimelineEntry | None:
        return self.entries[-1] if self.entries else None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.timeline_id:
            errors.append("timeline_id is required")
        if not self.entries:
            errors.append("timeline must have at least one entry")
        return errors


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LearningStatistics:
    stats_id: str
    domain: str
    strategy: str | None
    computed_at: str
    sample_size: int
    win_rate: float | None = None
    edge: float | None = None
    roi: float | None = None
    sharpe: float | None = None
    avg_confidence: float | None = None
    confidence_accuracy: float | None = None
    regime_stability: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.stats_id:
            errors.append("stats_id is required")
        for field_name, value in [
            ("win_rate", self.win_rate),
            ("avg_confidence", self.avg_confidence),
            ("confidence_accuracy", self.confidence_accuracy),
            ("regime_stability", self.regime_stability),
        ]:
            if value is not None and not 0.0 <= value <= 1.0:
                errors.append(f"{field_name} must be between 0 and 1")
        return errors


# ---------------------------------------------------------------------------
# Knowledge
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LearningKnowledge:
    """Distilled knowledge extracted from the learning layer."""

    knowledge_id: str
    domain: str
    claim: str
    confidence: float
    derived_from: tuple[str, ...]
    validated: bool = False
    invalidated: bool = False
    created_at: str | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.knowledge_id:
            errors.append("knowledge_id is required")
        if not self.claim:
            errors.append("claim is required")
        if not 0.0 <= self.confidence <= 1.0:
            errors.append("confidence must be between 0 and 1")
        if self.validated and self.invalidated:
            errors.append("knowledge cannot be both validated and invalidated")
        return errors


# ---------------------------------------------------------------------------
# Repository and pipeline interfaces
# ---------------------------------------------------------------------------


class UniversalLearningRepository:
    """Abstract read-only repository. Concrete implementations must be passive."""

    def save_snapshot(self, snapshot: LearningSnapshot) -> None:
        raise NotImplementedError

    def load_snapshot(self, snapshot_id: str) -> LearningSnapshot | None:
        raise NotImplementedError

    def list_snapshots(self, domain: str, strategy: str | None = None) -> list[LearningSnapshot]:
        raise NotImplementedError

    def save_signal(self, signal: LearningSignal) -> None:
        raise NotImplementedError

    def list_signals(self, domain: str) -> list[LearningSignal]:
        raise NotImplementedError

    def save_knowledge(self, knowledge: LearningKnowledge) -> None:
        raise NotImplementedError

    def load_timeline(self, domain: str, strategy: str | None = None) -> LearningTimeline | None:
        raise NotImplementedError

    def load_statistics(self, domain: str, strategy: str | None = None) -> LearningStatistics | None:
        raise NotImplementedError


class UniversalLearningPipeline:
    """
    Abstract passive learning pipeline.
    Must not alter decisions, execute actions, or modify runtime.
    """

    ADVISORY_ONLY: bool = True
    CONTRACT_VERSION: str = LEARNING_CONTRACT_VERSION

    def ingest(self, source: LearningSource, payload: dict[str, Any]) -> LearningEvidence:
        raise NotImplementedError

    def snapshot(self, domain: str, strategy: str | None = None) -> LearningSnapshot:
        raise NotImplementedError

    def compute_statistics(self, domain: str, strategy: str | None = None) -> LearningStatistics:
        raise NotImplementedError

    def detect_signals(self, snapshot: LearningSnapshot) -> tuple[LearningSignal, ...]:
        raise NotImplementedError

    def build_timeline(self, domain: str, strategy: str | None = None) -> LearningTimeline:
        raise NotImplementedError

    def extract_knowledge(self, domain: str) -> tuple[LearningKnowledge, ...]:
        raise NotImplementedError
