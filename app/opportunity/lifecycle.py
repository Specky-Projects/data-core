"""Opportunity Lifecycle — Stage 5.

Tracks stage transitions:
  NEW → EARLY → GROWING → MATURE → DECLINING → ARCHIVED

Transitions are deterministic: driven only by evidence counts, source counts,
confidence, and composite score. No wall-clock.
"""

from __future__ import annotations

from app.adaptive_intelligence.dto import EvaluationContext
from app.opportunity.dto import (
    LifecycleStage,
    Opportunity,
    OpportunityEvolutionSnapshot,
    build_snapshot_id,
)


def _compute_lifecycle_stage(opp: Opportunity) -> LifecycleStage:
    """Deterministic lifecycle classification based on evidence-derived metrics."""
    score = opp.score.composite_score
    sources = len(opp.sources) + len({s for c in opp.correlations for s in c.source_ids})
    evidence_count = len(opp.evidence)

    # ARCHIVED: very low confidence or no evidence
    if opp.confidence < 0.05 or evidence_count == 0:
        return LifecycleStage.ARCHIVED

    # DECLINING: low composite score despite having been seen
    if score < 0.15:
        return LifecycleStage.DECLINING

    # MATURE: high confidence + broad source coverage + rich evidence
    if opp.confidence >= 0.7 and sources >= 4 and evidence_count >= 10:
        return LifecycleStage.MATURE

    # GROWING: confidence building, multiple sources
    if opp.confidence >= 0.45 and sources >= 3 and evidence_count >= 5:
        return LifecycleStage.GROWING

    # EARLY: initial signals present
    if opp.confidence >= 0.25 and sources >= 2:
        return LifecycleStage.EARLY

    return LifecycleStage.NEW


def advance_lifecycle(
    opportunities: list[Opportunity],
    evaluation_context: EvaluationContext,
) -> list[Opportunity]:
    """Advance lifecycle stage for all opportunities and record snapshots."""
    for opp in opportunities:
        new_stage = _compute_lifecycle_stage(opp)
        previous = opp.lifecycle_stage
        opp.lifecycle_stage = new_stage

        if new_stage != previous:
            opp.explanation.lifecycle_rationale = (
                f"Stage transitioned from {previous.value} → {new_stage.value}. "
                f"Confidence={opp.confidence:.3f}, "
                f"score={opp.score.composite_score:.3f}, "
                f"evidence={len(opp.evidence)}, "
                f"sources={len(opp.sources)}."
            )
        else:
            opp.explanation.lifecycle_rationale = (
                f"Stage stable: {new_stage.value}. "
                f"Confidence={opp.confidence:.3f}, score={opp.score.composite_score:.3f}."
            )

        # Record snapshot
        snapshot = OpportunityEvolutionSnapshot(
            snapshot_id=build_snapshot_id(opp.opportunity_id, evaluation_context.evaluation_timestamp),
            opportunity_id=opp.opportunity_id,
            evaluation_timestamp=evaluation_context.evaluation_timestamp,
            confidence=opp.confidence,
            priority=opp.priority,
            composite_score=opp.score.composite_score,
            lifecycle_stage=new_stage,
            evidence_count=len(opp.evidence),
            source_count=len(opp.sources),
            entity_count=len(opp.entities),
        )
        opp.evolution_history.append(snapshot)
        opp.updated_at = evaluation_context.evaluation_timestamp

    return opportunities
