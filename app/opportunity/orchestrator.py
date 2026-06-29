"""Opportunity Pipeline Orchestrator — Business OS 1.5.

Full pipeline:
  KnowledgeReport → Discovery → Scoring → Lifecycle → Ranking → Portfolio → Health → OpportunityReport

Every stage is deterministic. All timestamps from EvaluationContext.
Consumes KnowledgeReport from app.knowledge — never bypasses it.
"""

from __future__ import annotations

import logging

from app.adaptive_intelligence.dto import EvaluationContext
from app.knowledge.dto import KnowledgeReport, _k_stable_hash
from app.opportunity.discovery import (
    discover_from_correlations,
    discover_from_knowledge_items,
)
from app.opportunity.dto import (
    OpportunityReport,
    OpportunityVersionMetadata,
    RankingStrategy,
)
from app.opportunity.evolution import annotate_evolution
from app.opportunity.health import compute_opportunity_health
from app.opportunity.learning import apply_adaptive_calibration, build_opportunity_feedback
from app.opportunity.lifecycle import advance_lifecycle
from app.opportunity.portfolio import build_portfolio
from app.opportunity.ranking import rank_opportunities
from app.opportunity.scoring import rescore_all

logger = logging.getLogger(__name__)


def run_opportunity_pipeline(
    knowledge_report: KnowledgeReport,
    evaluation_context: EvaluationContext,
    ranking_strategy: RankingStrategy = RankingStrategy.BY_COMPOSITE,
    min_source_count: int = 2,
    strategy_feedback: dict | None = None,
) -> OpportunityReport:
    """Execute the full Opportunity pipeline from a KnowledgeReport.

    Stages:
      1. Discovery (from items + correlations)
      2. Scoring (evidence-derived rescoring)
      3. Learning calibration (Adaptive Intelligence integration)
      4. Lifecycle advancement
      5. Evolution annotation
      6. Ranking
      7. Portfolio construction
      8. Health computation
    """
    items = knowledge_report.items
    correlations = knowledge_report.correlations

    # ── Stage 1: Discovery ────────────────────────────────────────────────────
    item_opps = discover_from_knowledge_items(
        items, evaluation_context, min_source_count=min_source_count
    )
    corr_opps = discover_from_correlations(correlations, items, evaluation_context)

    # Merge, deduplicate by opportunity_id
    seen_ids: set[str] = set()
    all_opps = []
    for opp in item_opps + corr_opps:
        if opp.opportunity_id not in seen_ids:
            seen_ids.add(opp.opportunity_id)
            all_opps.append(opp)

    logger.debug("discovered=%d (items=%d corr=%d)", len(all_opps), len(item_opps), len(corr_opps))

    if not all_opps:
        health = compute_opportunity_health([], evaluation_context)
        return OpportunityReport(
            report_id=_k_stable_hash({"empty": True, "ts": evaluation_context.evaluation_timestamp.isoformat()}),
            opportunities=[],
            ranked_opportunities=[],
            portfolio=[],
            health=health,
            versions=OpportunityVersionMetadata(),
            evaluation_context=evaluation_context,
            generated_at=evaluation_context.evaluation_timestamp,
            ranking_strategy=ranking_strategy,
            knowledge_item_count=len(items),
        )

    # ── Stage 2: Scoring ──────────────────────────────────────────────────────
    all_opps = rescore_all(all_opps, evaluation_context)

    # ── Stage 3: Adaptive Learning calibration ────────────────────────────────
    all_opps = apply_adaptive_calibration(all_opps, evaluation_context, strategy_feedback)

    # ── Stage 4: Lifecycle advancement ────────────────────────────────────────
    all_opps = advance_lifecycle(all_opps, evaluation_context)

    # ── Stage 5: Evolution annotation ────────────────────────────────────────
    all_opps = annotate_evolution(all_opps)

    # ── Stage 6: Ranking ──────────────────────────────────────────────────────
    ranked = rank_opportunities(all_opps, strategy=ranking_strategy)

    # ── Stage 7: Portfolio ────────────────────────────────────────────────────
    portfolio = build_portfolio(all_opps)

    # ── Stage 8: Health ───────────────────────────────────────────────────────
    health = compute_opportunity_health(all_opps, evaluation_context)

    report_id = _k_stable_hash({
        "opp_ids": sorted(o.opportunity_id for o in all_opps),
        "ts": evaluation_context.evaluation_timestamp.isoformat(),
        "strategy": ranking_strategy.value,
    })

    return OpportunityReport(
        report_id=report_id,
        opportunities=all_opps,
        ranked_opportunities=ranked,
        portfolio=portfolio,
        health=health,
        versions=OpportunityVersionMetadata(),
        evaluation_context=evaluation_context,
        generated_at=evaluation_context.evaluation_timestamp,
        ranking_strategy=ranking_strategy,
        knowledge_item_count=len(items),
        metadata={"adaptive_feedback": build_opportunity_feedback(all_opps)},
    )
