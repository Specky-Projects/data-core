"""Mirror runtime consumer bindings.

MirrorScientificObserver records Mirror decisions as scientific artifacts. It
does not alter strategy, committee, position sizing, risk, kill switch,
executor, thresholds or operational rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.execution_ledger.contracts import LedgerEntryKind
from app.scientific_consumers.facts import from_mirror_decision
from app.scientific_consumers.runtime import (
    ScientificConsumerRuntime,
    ScientificConsumerRuntimeRecord,
)
from app.scientific_identity.contract import ScientificEntityType
from app.scientific_pipeline.contracts import StageStatus


class MirrorScientificObserver:
    """Read-only observer for already-produced Mirror decision records."""

    READ_ONLY = True
    ADVISORY_ONLY = True
    SHADOW_MODE = True

    def __init__(self, runtime: ScientificConsumerRuntime | None = None) -> None:
        self.runtime = runtime or ScientificConsumerRuntime()

    def observe(self, decision_record: dict[str, Any]) -> ScientificConsumerRuntimeRecord:
        facts = from_mirror_decision(decision_record)
        return self.runtime.materialize(facts)


@dataclass(frozen=True)
class MirrorScientificCoverage:
    observed_decisions: int
    scientific_identity_coverage: float
    pipeline_trace_coverage: float
    explainability_coverage: float
    replay_coverage: float
    ledger_coverage: float
    learning_feed_coverage: float

    def as_percentages(self) -> dict[str, float]:
        return {
            "scientific_identity_coverage": self.scientific_identity_coverage,
            "pipeline_trace_coverage": self.pipeline_trace_coverage,
            "explainability_coverage": self.explainability_coverage,
            "replay_coverage": self.replay_coverage,
            "ledger_coverage": self.ledger_coverage,
            "learning_feed_coverage": self.learning_feed_coverage,
        }


class MirrorScientificRuntimeBinding:
    """Shadow-mode Mirror binding with read-only audit snapshots and metrics."""

    READ_ONLY = True
    ADVISORY_ONLY = True
    SHADOW_MODE = True

    def __init__(self, observer: MirrorScientificObserver | None = None) -> None:
        self.observer = observer or MirrorScientificObserver()
        self._records: list[ScientificConsumerRuntimeRecord] = []

    def observe_decision(self, decision_record: dict[str, Any]) -> ScientificConsumerRuntimeRecord:
        original = dict(decision_record)
        record = self.observer.observe(decision_record)
        if decision_record != original:
            raise RuntimeError("Mirror decision record was mutated by scientific binding")
        self._records.append(record)
        return record

    def records(self) -> tuple[ScientificConsumerRuntimeRecord, ...]:
        return tuple(self._records)

    def coverage(self) -> MirrorScientificCoverage:
        total = len(self._records)

        def pct(count: int) -> float:
            return 100.0 if total == 0 else round((count / total) * 100.0, 2)

        identity = sum(1 for r in self._records if r.identity_chain.entries)
        trace = sum(1 for r in self._records if r.pipeline_trace.stages)
        explainability = sum(1 for r in self._records if r.explainability.validate() == [])
        replay = sum(1 for r in self._records if r.replay_manifest.validate() == [])
        ledger = sum(1 for r in self._records if r.ledger.validate() == [])
        learning = sum(1 for r in self._records if r.learning_signal.ADVISORY_ONLY)
        return MirrorScientificCoverage(
            observed_decisions=total,
            scientific_identity_coverage=pct(identity),
            pipeline_trace_coverage=pct(trace),
            explainability_coverage=pct(explainability),
            replay_coverage=pct(replay),
            ledger_coverage=pct(ledger),
            learning_feed_coverage=pct(learning),
        )

    def replay_deterministic(self, record: ScientificConsumerRuntimeRecord) -> bool:
        replayed = self.observer.runtime.pipeline.replay(record.replay_manifest)
        replay_trace = self.observer.runtime.pipeline.trace(record.pipeline_trace.pipeline_id)
        if replay_trace is None or replayed.status != record.pipeline_state.status:
            return False
        return tuple(s.output_hash for s in replay_trace.stages) == tuple(
            s.output_hash for s in record.pipeline_trace.stages
        )

    def dashboard_snapshot(self) -> dict[str, Any]:
        """Read-only audit snapshot. No database, endpoint, scheduler or worker."""
        rows = []
        for r in self._records:
            rows.append({
                "decision_id": r.facts.decision_id,
                "lineage_id": r.lineage_id,
                "candidate_id": r.facts.candidate_id,
                "verdict": r.facts.verdict,
                "action": r.facts.action,
                "pipeline_id": r.pipeline_trace.pipeline_id,
                "pipeline_stages": len(r.pipeline_trace.stages),
                "failed_stages": [s.stage.value for s in r.pipeline_trace.stages if s.status == StageStatus.FAILED],
                "has_observation": r.observation.validate() == [],
                "has_scientific_identity": ScientificEntityType.DECISION in r.identity_chain.entity_types(),
                "has_outcome_identity": ScientificEntityType.OUTCOME in r.identity_chain.entity_types(),
                "has_learning_identity": ScientificEntityType.LEARNING in r.identity_chain.entity_types(),
                "has_knowledge_identity": ScientificEntityType.KNOWLEDGE in r.identity_chain.entity_types(),
                "has_explainability": r.explainability.validate() == [],
                "has_replay": r.replay_manifest.validate() == [],
                "has_ledger": r.ledger.validate() == [],
                "has_signal_entry": bool(r.ledger.entries_by_kind(LedgerEntryKind.EVIDENCE)),
                "has_execution_attempt_entry": bool(r.ledger.entries_by_kind(LedgerEntryKind.PREVIEW)),
                "has_replay_reference": bool(r.ledger.entries_by_kind(LedgerEntryKind.REPLAY)),
                "has_learning_feed": r.learning_signal.ADVISORY_ONLY,
            })
        return {
            "mode": "SHADOW_READ_ONLY",
            "mutable": False,
            "coverage": self.coverage().as_percentages(),
            "decisions": tuple(rows),
        }


MirrorPipelineTrace = MirrorScientificObserver
MirrorScientificIdentityAdapter = MirrorScientificObserver
MirrorReplayBinding = MirrorScientificObserver
MirrorExplainabilityBinding = MirrorScientificObserver
MirrorLedgerBinding = MirrorScientificObserver
