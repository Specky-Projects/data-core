"""Opportunity Learning Integration — Stage 10.

Integrates Opportunity Intelligence with Adaptive Intelligence.
Reuses the existing Adaptive Intelligence engine — no duplicate learning logic.

Learning improves:
  - Future opportunity discovery (confidence calibration)
  - Future ranking (priority calibration)

Mechanism:
  - Read existing recommendation_evolution / strategy_intelligence from DB
  - Use it to adjust opportunity confidence and priority post-scoring
  - Write back opportunity quality signals as new strategy feedback

This module is intentionally thin — it bridges, never duplicates.
"""

from __future__ import annotations

import logging
from typing import Any

from app.adaptive_intelligence.dto import EvaluationContext
from app.opportunity.dto import Opportunity, OpportunityVersionMetadata

logger = logging.getLogger(__name__)


def apply_adaptive_calibration(
    opportunities: list[Opportunity],
    evaluation_context: EvaluationContext,
    strategy_feedback: dict[str, Any] | None = None,
) -> list[Opportunity]:
    """Apply adaptive calibration from Adaptive Intelligence to opportunities.

    strategy_feedback: optional dict from AdaptiveIntelligence with calibration signals.
    If None (or no DB), operates in pass-through mode (no calibration).

    Calibration is additive and bounded — never overwrites evidence-derived scores,
    only applies a multiplier within [0.8, 1.2].
    """
    if not strategy_feedback:
        logger.debug("No strategy_feedback provided — adaptive calibration skipped.")
        return opportunities

    # Extract calibration multiplier from feedback (if available)
    calibration_factor = float(strategy_feedback.get("calibration_factor", 1.0))
    calibration_factor = max(0.8, min(1.2, calibration_factor))

    for opp in opportunities:
        opp.confidence = round(min(1.0, opp.confidence * calibration_factor), 4)
        opp.priority = round(min(1.0, opp.priority * calibration_factor), 4)
        opp.explanation.confidence_rationale += (
            f" Adaptive calibration applied: factor={calibration_factor:.3f}."
        )

    return opportunities


def build_opportunity_feedback(
    opportunities: list[Opportunity],
) -> dict[str, Any]:
    """Build feedback signals to feed back into Adaptive Intelligence.

    Returns a summary that the Adaptive layer can use to improve future quality.
    No direct DB write here — caller decides whether to persist.
    """
    if not opportunities:
        return {"opportunity_count": 0, "avg_confidence": 0.0, "avg_composite": 0.0}

    n = len(opportunities)
    return {
        "opportunity_count": n,
        "avg_confidence": round(sum(o.confidence for o in opportunities) / n, 4),
        "avg_composite": round(sum(o.score.composite_score for o in opportunities) / n, 4),
        "avg_novelty": round(sum(o.novelty for o in opportunities) / n, 4),
        "lifecycle_distribution": {
            stage: sum(1 for o in opportunities if o.lifecycle_stage.value == stage)
            for stage in ["new", "early", "growing", "mature", "declining", "archived"]
        },
        "versions": OpportunityVersionMetadata().model_dump(mode="json"),
    }
