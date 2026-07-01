"""Universal Learning binding for scientific runtime consumers.

This module consumes the existing Universal Learning contract in
ADVISORY_ONLY mode. It derives passive evidence/snapshot/signal objects from a
consumer decision without feeding anything back into operational execution.
"""
from __future__ import annotations

from app.scientific_consumers.facts import DecisionFacts
from app.scientific_identity.contract import stable_hash
from app.universal_learning.contracts import (
    LearningEvidence,
    LearningKnowledge,
    LearningMaturity,
    LearningSignal,
    LearningSignalKind,
    LearningSnapshot,
    LearningSource,
    LearningStatistics,
    LearningTimeline,
    LearningTimelineEntry,
)


def _source_for(facts: DecisionFacts) -> LearningSource:
    if facts.consumer == "mirror":
        return LearningSource.MIRROR
    if facts.outcome is not None:
        return LearningSource.OUTCOME
    return LearningSource.EVIDENCE


def build_learning_evidence(facts: DecisionFacts) -> LearningEvidence:
    payload = {
        "lineage_id": facts.lineage_id,
        "decision_id": facts.decision_id,
        "consumer": facts.consumer,
        "verdict": facts.verdict,
        "action": facts.action,
        "confidence": facts.confidence,
        "outcome": facts.outcome.kind if facts.outcome else None,
    }
    return LearningEvidence(
        evidence_id=stable_hash({"lineage": facts.lineage_id, "kind": "learning_evidence"}),
        source=_source_for(facts),
        source_ref=facts.decision_id,
        captured_at=facts.outcome.recorded_at if facts.outcome else facts.decided_at,
        payload_hash=stable_hash(payload),
        quality_score=facts.confidence,
        metadata={"advisory_only": True, "consumer": facts.consumer},
    )


def build_learning_snapshot(facts: DecisionFacts) -> LearningSnapshot:
    evidence = build_learning_evidence(facts)
    return LearningSnapshot(
        snapshot_id=stable_hash({"lineage": facts.lineage_id, "kind": "learning_snapshot"}),
        domain=facts.domain,
        strategy=facts.strategy,
        captured_at=evidence.captured_at,
        maturity=LearningMaturity.BOOTSTRAP,
        sample_size=1,
        evidence_refs=(evidence.evidence_id,),
        metrics={
            "confidence": facts.confidence,
            "posterior": facts.posterior,
            "evidence_weight": facts.evidence_weight,
        },
        metadata={"advisory_only": True, "consumer": facts.consumer},
    )


def build_learning_signal(facts: DecisionFacts) -> LearningSignal:
    snapshot = build_learning_snapshot(facts)
    if facts.outcome is None:
        kind = LearningSignalKind.CONFIDENCE_DRIFT
        direction = "NEUTRAL"
        description = "Passive advisory signal from supervised recommendation."
        magnitude = facts.confidence
    elif facts.outcome.kind == "SUCCESS":
        kind = LearningSignalKind.EDGE_CONFIRMATION
        direction = "POSITIVE"
        description = "Outcome passively confirms the recorded expected edge."
        magnitude = min(1.0, abs((facts.outcome.realized_value or 0.0) - (facts.outcome.expected_value or 0.0)))
    else:
        kind = LearningSignalKind.OUTCOME_ANOMALY
        direction = "NEGATIVE"
        description = "Outcome differs from the recorded expected edge."
        magnitude = facts.confidence

    return LearningSignal(
        signal_id=stable_hash({"lineage": facts.lineage_id, "kind": "learning_signal"}),
        kind=kind,
        domain=facts.domain,
        strategy=facts.strategy,
        detected_at=snapshot.captured_at,
        snapshot_ref=snapshot.snapshot_id,
        magnitude=magnitude,
        direction=direction,
        description=description,
        evidence_refs=snapshot.evidence_refs,
        metadata={"advisory_only": True, "consumer": facts.consumer},
    )


def build_learning_statistics(facts: DecisionFacts) -> LearningStatistics:
    edge = None
    if facts.outcome and facts.outcome.realized_value is not None and facts.outcome.expected_value is not None:
        edge = facts.outcome.realized_value - facts.outcome.expected_value
    return LearningStatistics(
        stats_id=stable_hash({"lineage": facts.lineage_id, "kind": "learning_statistics"}),
        domain=facts.domain,
        strategy=facts.strategy,
        computed_at=facts.outcome.recorded_at if facts.outcome else facts.decided_at,
        sample_size=1,
        win_rate=1.0 if facts.outcome and facts.outcome.kind == "SUCCESS" else None,
        edge=edge,
        avg_confidence=facts.confidence,
        confidence_accuracy=None,
        regime_stability=None,
        metadata={"advisory_only": True, "consumer": facts.consumer},
    )


def build_learning_timeline(facts: DecisionFacts) -> LearningTimeline:
    snapshot = build_learning_snapshot(facts)
    signal = build_learning_signal(facts)
    entry = LearningTimelineEntry(
        entry_id=stable_hash({"lineage": facts.lineage_id, "kind": "learning_timeline_entry"}),
        snapshot_ref=snapshot.snapshot_id,
        recorded_at=snapshot.captured_at,
        maturity=snapshot.maturity,
        delta_metrics={"confidence": facts.confidence},
        signals=(signal.signal_id,),
    )
    day = (snapshot.captured_at or facts.decided_at)[:10]
    return LearningTimeline(
        timeline_id=stable_hash({"lineage": facts.lineage_id, "kind": "learning_timeline"}),
        domain=facts.domain,
        strategy=facts.strategy,
        entries=(entry,),
        from_date=day,
        to_date=day,
    )


def build_learning_knowledge(facts: DecisionFacts) -> tuple[LearningKnowledge, ...]:
    signal = build_learning_signal(facts)
    claim = (
        f"{facts.consumer} produced an advisory {facts.action} signal for "
        f"{facts.candidate_id} with confidence {facts.confidence:.2f}."
    )
    return (
        LearningKnowledge(
            knowledge_id=stable_hash({"lineage": facts.lineage_id, "kind": "learning_knowledge"}),
            domain=facts.domain,
            claim=claim,
            confidence=facts.confidence,
            derived_from=(signal.signal_id,),
            validated=facts.outcome is not None and facts.outcome.kind == "SUCCESS",
            invalidated=facts.outcome is not None and facts.outcome.kind == "FAILURE",
            created_at=facts.outcome.recorded_at if facts.outcome else facts.decided_at,
        ),
    )
