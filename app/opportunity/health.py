"""Opportunity Health — Stage 8.

10-dimension evidence-derived health model for the Opportunity layer.
Every metric derives from observable evidence in the opportunity set.
No wall-clock.
"""

from __future__ import annotations

from app.adaptive_intelligence.dto import EvaluationContext
from app.opportunity.dto import (
    OPPORTUNITY_VERSION,
    Opportunity,
    OpportunityHealth,
    OpportunityVersionMetadata,
)


def compute_opportunity_health(
    opportunities: list[Opportunity],
    evaluation_context: EvaluationContext,
) -> OpportunityHealth:
    """Compute 10-dimension health score from the opportunity set."""
    if not opportunities:
        return OpportunityHealth(
            evidence_quality=0.0, freshness=0.0, confidence=0.0, consistency=0.0,
            coverage=0.0, source_diversity=0.0, market_activity=0.0,
            historical_stability=0.0, novelty=0.0, explainability=0.0,
            health_score=0.0, opportunity_count=0,
        )

    n = len(opportunities)

    # 1. Evidence quality — avg evidence_strength across all opportunities
    evidence_quality = sum(o.score.evidence_strength for o in opportunities) / n

    # 2. Freshness — avg freshness score
    freshness = sum(o.score.freshness for o in opportunities) / n

    # 3. Confidence — avg confidence
    confidence = sum(o.confidence for o in opportunities) / n

    # 4. Consistency — avg consistency score
    consistency = sum(o.score.consistency for o in opportunities) / n

    # 5. Coverage — ratio of opportunities with ≥2 sources
    multi_source = sum(1 for o in opportunities if len(o.sources) >= 2 or len(o.correlations) >= 1)
    coverage = multi_source / n

    # 6. Source diversity — avg source_diversity score
    source_diversity = sum(o.score.source_diversity for o in opportunities) / n

    # 7. Market activity — avg market_impact score
    market_activity = sum(o.score.market_impact for o in opportunities) / n

    # 8. Historical stability — fraction of opps with evolution history
    with_history = sum(1 for o in opportunities if len(o.evolution_history) >= 1)
    historical_stability = with_history / n

    # 9. Novelty — avg novelty
    novelty = sum(o.novelty for o in opportunities) / n

    # 10. Explainability — fraction of opps with non-empty explanation
    with_explanation = sum(1 for o in opportunities if o.explanation.why_exists)
    explainability = with_explanation / n

    dims = [
        evidence_quality, freshness, confidence, consistency,
        coverage, source_diversity, market_activity,
        historical_stability, novelty, explainability,
    ]
    health_score = round(sum(dims) / len(dims), 4)

    return OpportunityHealth(
        evidence_quality=round(evidence_quality, 4),
        freshness=round(freshness, 4),
        confidence=round(confidence, 4),
        consistency=round(consistency, 4),
        coverage=round(coverage, 4),
        source_diversity=round(source_diversity, 4),
        market_activity=round(market_activity, 4),
        historical_stability=round(historical_stability, 4),
        novelty=round(novelty, 4),
        explainability=round(explainability, 4),
        health_score=health_score,
        opportunity_count=n,
        versions=OpportunityVersionMetadata(),
    )
