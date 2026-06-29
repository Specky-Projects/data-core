"""Opportunity Ranking — Stage 4.

Ranking is:
  - Deterministic: same input → same ranked order
  - Explainable: every rank exposes the key dimension
  - Reproducible: ranking strategy is embedded in the report
  - Stable: ties broken by opportunity_id (lexicographic) for determinism
"""

from __future__ import annotations

from app.opportunity.dto import Opportunity, RankingStrategy


def _rank_key(opp: Opportunity, strategy: RankingStrategy) -> tuple:
    """Build a sort key for the given strategy. Higher is better (negate for sort)."""
    s = opp.score
    if strategy == RankingStrategy.BY_CONFIDENCE:
        primary = opp.confidence
    elif strategy == RankingStrategy.BY_NOVELTY:
        primary = opp.novelty
    elif strategy == RankingStrategy.BY_IMPACT:
        primary = opp.impact
    elif strategy == RankingStrategy.BY_URGENCY:
        primary = opp.urgency
    elif strategy == RankingStrategy.BY_FRESHNESS:
        primary = s.freshness
    else:  # BY_COMPOSITE (default)
        primary = s.composite_score

    # Secondary: confidence; tertiary: opportunity_id (deterministic tiebreak)
    return (-round(primary, 6), -round(opp.confidence, 6), opp.opportunity_id)


def rank_opportunities(
    opportunities: list[Opportunity],
    strategy: RankingStrategy = RankingStrategy.BY_COMPOSITE,
) -> list[Opportunity]:
    """Return a new list of opportunities sorted by the given strategy.

    Stable, deterministic, and lexicographic tiebreak on opportunity_id.
    """
    ranked = sorted(opportunities, key=lambda o: _rank_key(o, strategy))

    # Annotate ranking rationale in explanation
    for rank, opp in enumerate(ranked, 1):
        opp.explanation.ranking_rationale = (
            f"Rank #{rank} by strategy '{strategy.value}': "
            f"composite={opp.score.composite_score:.3f}, "
            f"confidence={opp.confidence:.3f}, "
            f"novelty={opp.novelty:.3f}, "
            f"impact={opp.impact:.3f}."
        )

    return ranked
