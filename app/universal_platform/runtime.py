"""WS5 — Universal Observation Runtime.

Generalises the Phase 1 ``ScientificConsumerRuntime`` for *any* domain without
duplicating it. Given a ``UniversalEvent`` it returns a
``UniversalObservationRecord`` that carries exactly the artifacts every project
must produce:

    ObservationContract
    ScientificIdentity      (identity chain)
    PipelineTrace
    Explainability
    ReplayManifest
    ExecutionLedger         (when applicable)
    LearningFeed
    CoverageMetrics
    AuditSnapshot

The scientific chain is produced by reusing ``materialize()`` verbatim; this
module only adds the two platform-level artifacts (coverage + audit snapshot)
and a stable accessor surface for the daily brief and alert engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.observation.contract import ObservationContract, ObservationSnapshot, stable_hash
from app.scientific_consumers.runtime import (
    ScientificConsumerRuntime,
    ScientificConsumerRuntimeRecord,
)
from app.universal_platform.events import Severity, UniversalEvent, to_decision_facts

# The canonical set of scientific artifacts the universal runtime guarantees.
# "ledger" is applicable to every domain here (advisory ledger), so it counts.
COVERAGE_ARTIFACTS: tuple[str, ...] = (
    "observation",
    "scientific_identity",
    "pipeline_trace",
    "explainability",
    "replay_manifest",
    "execution_ledger",
    "learning_feed",
)


@dataclass(frozen=True)
class CoverageMetrics:
    """How completely an observation was materialised into the chain."""

    expected: tuple[str, ...]
    present: tuple[str, ...]
    missing: tuple[str, ...]
    coverage_ratio: float
    validation_errors: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return not self.missing and not self.validation_errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "expected": list(self.expected),
            "present": list(self.present),
            "missing": list(self.missing),
            "coverage_ratio": self.coverage_ratio,
            "validation_errors": list(self.validation_errors),
            "is_complete": self.is_complete,
        }


@dataclass(frozen=True)
class AuditSnapshot:
    """Immutable, replayable proof of what was observed and how completely."""

    snapshot_id: str
    lineage_id: str
    captured_at: str
    observation_snapshot: ObservationSnapshot
    record_hash: str
    coverage: CoverageMetrics

    def verify(self, observation: ObservationContract) -> bool:
        return self.observation_snapshot.verify(observation)

    def as_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "lineage_id": self.lineage_id,
            "captured_at": self.captured_at,
            "observation_id": self.observation_snapshot.observation_id,
            "observation_hash": self.observation_snapshot.observation_hash,
            "record_hash": self.record_hash,
            "coverage": self.coverage.as_dict(),
        }


@dataclass(frozen=True)
class UniversalObservationRecord:
    """The universal, per-event scientific bundle produced for every project."""

    event: UniversalEvent
    scientific: ScientificConsumerRuntimeRecord
    coverage: CoverageMetrics
    audit: AuditSnapshot
    advisory_only: bool = True
    shadow_mode: bool = True
    read_only: bool = True

    # ── stable accessor surface (used by brief + alert engine) ───────────────
    @property
    def lineage_id(self) -> str:
        return self.scientific.lineage_id

    @property
    def observation(self) -> ObservationContract:
        return self.scientific.observation

    @property
    def pipeline_id(self) -> str:
        return self.scientific.pipeline_trace.pipeline_id

    @property
    def severity(self) -> Severity:
        return self.event.severity

    @property
    def learning_feed(self) -> dict[str, Any]:
        s = self.scientific
        return {
            "evidence": s.learning_evidence,
            "snapshot": s.learning_snapshot,
            "signal": s.learning_signal,
            "statistics": s.learning_statistics,
            "timeline": s.learning_timeline,
            "knowledge": s.learning_knowledge,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event.event_id,
            "project": self.event.project,
            "domain": self.event.domain,
            "event_type": self.event.event_type,
            "entity_id": self.event.entity_id,
            "severity": self.event.severity.value,
            "lineage_id": self.lineage_id,
            "observation_id": self.observation.observation_id,
            "pipeline_id": self.pipeline_id,
            "coverage": self.coverage.as_dict(),
            "audit": self.audit.as_dict(),
            "advisory_only": self.advisory_only,
            "shadow_mode": self.shadow_mode,
            "read_only": self.read_only,
        }


def _build_coverage(record: ScientificConsumerRuntimeRecord) -> CoverageMetrics:
    present: list[str] = []
    values = {
        "observation": record.observation,
        "scientific_identity": record.identity_chain,
        "pipeline_trace": record.pipeline_trace,
        "explainability": record.explainability,
        "replay_manifest": record.replay_manifest,
        "execution_ledger": record.ledger,
        "learning_feed": record.learning_evidence,
    }
    for name in COVERAGE_ARTIFACTS:
        if values.get(name) is not None:
            present.append(name)
    missing = tuple(a for a in COVERAGE_ARTIFACTS if a not in present)
    ratio = len(present) / len(COVERAGE_ARTIFACTS) if COVERAGE_ARTIFACTS else 1.0
    return CoverageMetrics(
        expected=COVERAGE_ARTIFACTS,
        present=tuple(present),
        missing=missing,
        coverage_ratio=round(ratio, 4),
        validation_errors=tuple(record.validate()),
    )


def _build_audit(
    event: UniversalEvent,
    record: ScientificConsumerRuntimeRecord,
    coverage: CoverageMetrics,
) -> AuditSnapshot:
    obs_snapshot = ObservationSnapshot.from_observation(record.observation, event.occurred_at)
    record_hash = stable_hash(
        {
            "observation": record.observation.payload_hash,
            "pipeline": record.pipeline_trace.pipeline_id,
            "replay_inputs": [ri.payload_hash for ri in record.replay_manifest.replay_inputs],
            "lineage": record.lineage_id,
        }
    )
    return AuditSnapshot(
        snapshot_id=stable_hash({"lineage": record.lineage_id, "captured_at": event.occurred_at}),
        lineage_id=record.lineage_id,
        captured_at=event.occurred_at,
        observation_snapshot=obs_snapshot,
        record_hash=record_hash,
        coverage=coverage,
    )


class UniversalObservationRuntime:
    """Pure, deterministic materializer for any project's events."""

    ADVISORY_ONLY = True
    SHADOW_MODE = True
    READ_ONLY = True

    def __init__(self, runtime: ScientificConsumerRuntime | None = None) -> None:
        self.runtime = runtime or ScientificConsumerRuntime()

    def observe(self, event: UniversalEvent) -> UniversalObservationRecord:
        errors = event.validate()
        if errors:
            raise ValueError(f"invalid UniversalEvent: {'; '.join(errors)}")
        facts = to_decision_facts(event)
        scientific = self.runtime.materialize(facts)
        coverage = _build_coverage(scientific)
        audit = _build_audit(event, scientific, coverage)
        return UniversalObservationRecord(
            event=event,
            scientific=scientific,
            coverage=coverage,
            audit=audit,
        )

    def coverage(self, event: UniversalEvent) -> CoverageMetrics:
        return self.observe(event).coverage

    def snapshot(self, event: UniversalEvent) -> AuditSnapshot:
        return self.observe(event).audit
