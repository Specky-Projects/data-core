"""Opportunity Scoring — Stage 3.

Evidence-derived scoring across 10 dimensions.
Every score exposes its evidence basis.
No arbitrary weights — all dimensions derive from observable evidence.
"""

from __future__ import annotations

from app.adaptive_intelligence.dto import EvaluationContext
from app.opportunity.dto import (
    Opportunity,
    OpportunityScore,
    OpportunityVersionMetadata,
)


def score_opportunity(
    opp: Opportunity,
    evaluation_context: EvaluationContext,
) -> OpportunityScore:
    """Recompute a fully evidence-derived score for the opportunity.

    Called after discovery to finalize scores with any additional context.
    """
    items_count = len(opp.evidence)
    source_count = len(opp.sources)
    entity_count = len(opp.entities)
    corr_count = len(opp.correlations)

    # Freshness: average of evidence timestamps
    evidence_with_ts = [ev for ev in opp.evidence if ev.timestamp and ev.timestamp.year > 1970]
    if evidence_with_ts:
        import math
        ref_ts = evaluation_context.evaluation_timestamp.timestamp()
        ages = [(ref_ts - ev.timestamp.timestamp()) / 86_400.0 for ev in evidence_with_ts]
        avg_age = sum(ages) / len(ages)
        freshness = round(max(0.05, math.exp(-avg_age / 30.0)), 4)
    else:
        freshness = opp.score.freshness or 0.05

    evidence_strength = min(1.0, items_count / 10.0)
    source_diversity = min(1.0, source_count / 4.0)
    novelty = opp.novelty
    confidence = opp.confidence
    growth_velocity = min(1.0, (items_count + corr_count) / 15.0)
    risk = round(max(0.0, 1.0 - confidence), 4)
    market_impact = min(1.0, opp.impact)
    strategic_relevance = min(1.0, confidence * 0.6 + source_diversity * 0.4)
    consistency = min(1.0, evidence_strength * 0.5 + source_diversity * 0.5)

    evidence_ids = [ev.evidence_id for ev in opp.evidence[:10]]

    score = OpportunityScore(
        novelty=round(novelty, 4),
        evidence_strength=round(evidence_strength, 4),
        source_diversity=round(source_diversity, 4),
        growth_velocity=round(growth_velocity, 4),
        confidence=round(confidence, 4),
        risk=round(risk, 4),
        market_impact=round(market_impact, 4),
        strategic_relevance=round(strategic_relevance, 4),
        consistency=round(consistency, 4),
        freshness=round(freshness, 4),
        evidence_ids=evidence_ids,
    )
    return score


def rescore_all(
    opportunities: list[Opportunity],
    evaluation_context: EvaluationContext,
) -> list[Opportunity]:
    """Apply evidence-derived rescoring to all opportunities in-place."""
    for opp in opportunities:
        opp.score = score_opportunity(opp, evaluation_context)
        opp.priority = round(opp.score.composite_score, 4)
    return opportunities
