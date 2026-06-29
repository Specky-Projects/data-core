"""Opportunity Evolution — Stage 6.

Tracks how opportunities change over time:
  - Confidence evolution
  - Priority evolution
  - Evidence evolution
  - Source evolution
  - Direction classification

All calculations are deterministic and evidence-derived.
"""

from __future__ import annotations

from app.opportunity.dto import (
    EvolutionDirection,
    Opportunity,
    OpportunityEvolutionSnapshot,
)


def compute_evolution_direction(snapshots: list[OpportunityEvolutionSnapshot]) -> EvolutionDirection:
    """Classify the trend direction from the evolution history.

    Requires at least 2 snapshots to determine direction.
    """
    if len(snapshots) < 2:
        return EvolutionDirection.UNKNOWN

    # Compare most recent pair
    first = snapshots[0]
    last = snapshots[-1]

    delta_confidence = last.confidence - first.confidence
    delta_score = last.composite_score - first.composite_score
    combined_delta = (delta_confidence + delta_score) / 2.0

    if combined_delta >= 0.05:
        return EvolutionDirection.IMPROVING
    if combined_delta <= -0.05:
        return EvolutionDirection.DECLINING
    return EvolutionDirection.STABLE


def build_evolution_explanation(opp: Opportunity) -> str:
    """Produce a human-readable explanation of the opportunity's evolution."""
    history = opp.evolution_history
    if not history:
        return "No evolution history available."

    direction = compute_evolution_direction(history)
    first = history[0]
    last = history[-1]

    delta_conf = last.confidence - first.confidence
    delta_score = last.composite_score - first.composite_score
    delta_evid = last.evidence_count - first.evidence_count
    delta_sources = last.source_count - first.source_count

    lines = [
        f"Direction: {direction.value.upper()}",
        f"Snapshots: {len(history)}",
        f"Confidence: {first.confidence:.3f} → {last.confidence:.3f} (Δ {delta_conf:+.3f})",
        f"Score: {first.composite_score:.3f} → {last.composite_score:.3f} (Δ {delta_score:+.3f})",
        f"Evidence: {first.evidence_count} → {last.evidence_count} (Δ {delta_evid:+d})",
        f"Sources: {first.source_count} → {last.source_count} (Δ {delta_sources:+d})",
        f"Lifecycle: {first.lifecycle_stage.value} → {last.lifecycle_stage.value}",
    ]
    return " | ".join(lines)


def annotate_evolution(opportunities: list[Opportunity]) -> list[Opportunity]:
    """Annotate each opportunity with its evolution explanation."""
    for opp in opportunities:
        if len(opp.evolution_history) >= 2:
            direction = compute_evolution_direction(opp.evolution_history)
            explanation = build_evolution_explanation(opp)
            opp.explanation.confidence_rationale = (
                opp.explanation.confidence_rationale
                + f" Evolution: {direction.value}. {explanation}"
            )
    return opportunities
