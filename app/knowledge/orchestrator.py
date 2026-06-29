"""Knowledge Pipeline Orchestrator — Business OS 1.4.

Ties connectors → entity resolution → fusion → correlation → graph → health
into a single deterministic KnowledgeReport.
All computations are anchored to evaluation_context.evaluation_timestamp.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.adaptive_intelligence.dto import EvaluationContext
from app.knowledge.connectors.base import AbstractKnowledgeConnector
from app.knowledge.correlation import (
    compute_cross_source_correlations,
    compute_entity_co_occurrence,
)
from app.knowledge.dto import (
    KnowledgeReport,
    KnowledgeVersionMetadata,
    _k_stable_hash,
    compute_knowledge_health,
)
from app.knowledge.graph import build_knowledge_graph
from app.knowledge.knowledge_fusion import fuse_knowledge_items

logger = logging.getLogger(__name__)


def run_knowledge_pipeline(
    connectors: list[AbstractKnowledgeConnector],
    evaluation_context: EvaluationContext,
    fusion_threshold: float = 0.3,
    correlation_window_days: int = 30,
    min_correlation_sources: int = 2,
    min_correlation_mentions: int = 2,
) -> KnowledgeReport:
    """Execute the full knowledge pipeline and return a KnowledgeReport.

    Pipeline stages:
      1. Ingest (all connectors, in order)
      2. Knowledge Fusion (cross-source de-duplication)
      3. Cross-Source Correlations
      4. Entity Co-Occurrence Correlations
      5. Logical Knowledge Graph (relationships)
      6. Knowledge Health
    """
    # ── Stage 1: Ingest ────────────────────────────────────────────────────────
    all_items = []
    for connector in connectors:
        try:
            items = connector.ingest(evaluation_context)
            all_items.extend(items)
            logger.debug("connector=%s fetched=%d", connector.connector_name, len(items))
        except Exception as exc:
            logger.warning("connector=%s failed: %s", connector.connector_name, exc)

    # ── Stage 2: Knowledge Fusion ──────────────────────────────────────────────
    fused = fuse_knowledge_items(all_items, threshold=fusion_threshold)

    # ── Stage 3 & 4: Correlations ──────────────────────────────────────────────
    cross_source = compute_cross_source_correlations(
        all_items,
        evaluation_context,
        window_days=correlation_window_days,
        min_sources=min_correlation_sources,
        min_mentions=min_correlation_mentions,
    )
    co_occurrence = compute_entity_co_occurrence(
        all_items,
        evaluation_context,
        window_days=correlation_window_days,
    )
    correlations = cross_source + co_occurrence

    # ── Stage 5: Logical Knowledge Graph ──────────────────────────────────────
    graph = build_knowledge_graph(all_items)
    relationships = graph.all_relationships()

    # ── Stage 6: Knowledge Health ──────────────────────────────────────────────
    health = compute_knowledge_health(
        items=all_items,
        fused=fused,
        correlations=correlations,
        relationships=relationships,
        evaluation_context=evaluation_context,
    )

    report_id = _k_stable_hash({
        "items": sorted(i.item_id for i in all_items),
        "eval_ts": evaluation_context.evaluation_timestamp.isoformat(),
    })

    return KnowledgeReport(
        report_id=report_id,
        items=all_items,
        fused_items=fused,
        correlations=correlations,
        relationships=relationships,
        health=health,
        versions=KnowledgeVersionMetadata(),
        evaluation_context=evaluation_context,
        generated_at=evaluation_context.evaluation_timestamp,
    )
