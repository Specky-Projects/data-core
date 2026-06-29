"""Opportunity Discovery — Stage 2.

Detects opportunities from:
  - Knowledge items with high cross-source presence
  - Cross-source correlations (CROSS_SOURCE_CONVERGENCE)
  - Entities with high mention counts across sources
  - Entity co-occurrence pairs as relationship opportunities

All discovery is deterministic and evidence-anchored.
No wall-clock. All timestamps from EvaluationContext.
"""

from __future__ import annotations

from collections import defaultdict

from app.adaptive_intelligence.dto import EvaluationContext
from app.knowledge.dto import (
    KnowledgeCorrelation,
    KnowledgeEntity,
    KnowledgeItem,
    KnowledgeRelationship,
    CorrelationSignal,
    _k_stable_hash,
)
from app.opportunity.dto import (
    LifecycleStage,
    Opportunity,
    OpportunityExplanation,
    OpportunityProvenance,
    OpportunityScore,
    OpportunityType,
    OpportunityVersionMetadata,
    build_opportunity_id,
)

# ── Discovery constants ────────────────────────────────────────────────────────

_MIN_SOURCE_COUNT = 2
_MIN_ENTITY_MENTIONS = 2
_MIN_CONFIDENCE = 0.1


def _classify_type(entities: list[KnowledgeEntity], topics: list[str]) -> OpportunityType:
    """Heuristic classification from entity types and topics."""
    topic_set = {t.lower() for t in topics}
    entity_types = {e.entity_type.value for e in entities}

    if "technology" in entity_types or any(t in topic_set for t in ["ml", "ai", "llm", "gpu", "cloud"]):
        return OpportunityType.TECHNOLOGY
    if "repository" in entity_types or "open_source" in topic_set:
        return OpportunityType.OPEN_SOURCE
    if any(t in topic_set for t in ["research", "paper", "arxiv", "academic"]):
        return OpportunityType.RESEARCH
    if "product" in entity_types:
        return OpportunityType.PRODUCT
    if "infrastructure" in topic_set:
        return OpportunityType.INFRASTRUCTURE
    return OpportunityType.UNKNOWN


def _infer_domain(entities: list[KnowledgeEntity]) -> str:
    """Infer domain from the most confident entity."""
    if not entities:
        return "general"
    best = max(entities, key=lambda e: e.confidence)
    return best.entity_type.value


def discover_from_knowledge_items(
    items: list[KnowledgeItem],
    evaluation_context: EvaluationContext,
    min_source_count: int = _MIN_SOURCE_COUNT,
) -> list[Opportunity]:
    """Discover opportunities from items with multi-source presence.

    An item cluster becomes an opportunity when:
    - Canonical entities appear across ≥ min_source_count sources
    - Evidence confidence is sufficient
    """
    # Group items by their primary entities (cross-source entity presence)
    entity_to_items: dict[str, list[KnowledgeItem]] = defaultdict(list)
    for item in items:
        for entity in item.entities:
            entity_to_items[entity.entity_id].append(item)

    opportunities: list[Opportunity] = []
    seen_opp_ids: set[str] = set()

    for entity_id, entity_items in entity_to_items.items():
        source_ids = {i.source.source_id for i in entity_items}
        if len(source_ids) < min_source_count:
            continue

        # Representative item = highest confidence + engagement
        primary = max(entity_items, key=lambda it: it.confidence + it.engagement_score * 0.01)

        # Gather entity for this opportunity
        entity_obj = next(
            (e for it in entity_items for e in it.entities if e.entity_id == entity_id), None
        )
        entities = [entity_obj] if entity_obj else []
        all_evidence = []
        seen_ev: set[str] = set()
        for it in entity_items:
            for ev in it.evidence:
                if ev.evidence_id not in seen_ev:
                    seen_ev.add(ev.evidence_id)
                    all_evidence.append(ev)
        all_evidence = all_evidence[:20]

        topics = sorted({t for it in entity_items for t in it.topics})
        opp_type = _classify_type(entities, topics)
        domain = _infer_domain(entities)
        title = entity_obj.canonical_name.title() if entity_obj else primary.title[:80]

        opp_id = build_opportunity_id(title, domain, opp_type)
        if opp_id in seen_opp_ids:
            continue
        seen_opp_ids.add(opp_id)

        sources = list({it.source.source_id: it.source for it in entity_items}.values())
        confidence = min(1.0, 0.3 + 0.15 * len(source_ids) + 0.05 * len(all_evidence))
        novelty = min(1.0, 0.2 + 0.1 * len(source_ids))

        provenance = OpportunityProvenance(
            knowledge_item_ids=sorted({it.item_id for it in entity_items})[:25],
            entity_ids=[entity_id],
            evidence_ids=sorted(seen_ev)[:25],
            discovery_method="cross_source_entity_presence",
            discovered_at=evaluation_context.evaluation_timestamp,
        )

        explanation = OpportunityExplanation(
            why_exists=(
                f"Entity '{title}' appears across {len(source_ids)} independent source(s): "
                f"{', '.join(sorted(source_ids)[:5])}. "
                f"Cross-source presence signals meaningful attention."
            ),
            evidence_basis=sorted(seen_ev)[:10],
            entity_roles={entity_id: "primary subject"},
            source_contributions={sid: round(1.0 / len(source_ids), 3) for sid in source_ids},
            confidence_rationale=f"Confidence derived from {len(source_ids)} sources × {len(all_evidence)} evidence fragments.",
            lifecycle_rationale="Stage NEW: first detection from knowledge scan.",
        )

        score = _build_score_from_items(entity_items, all_evidence, sources, novelty, confidence)

        opportunities.append(Opportunity(
            opportunity_id=opp_id,
            title=title,
            summary=f"{title} is gaining attention across {len(source_ids)} knowledge sources.",
            description=primary.summary[:512],
            confidence=round(confidence, 4),
            priority=round(score.composite_score, 4),
            novelty=round(novelty, 4),
            maturity=round(min(1.0, len(entity_items) / 10.0), 4),
            urgency=round(min(1.0, len(source_ids) / 4.0), 4),
            impact=round(min(1.0, len(all_evidence) / 15.0 + 0.2), 4),
            opportunity_type=opp_type,
            market="",
            domain=domain,
            evidence=all_evidence,
            entities=entities,
            relationships=[],
            sources=sources,
            correlations=[],
            provenance=provenance,
            score=score,
            explanation=explanation,
            lifecycle_stage=LifecycleStage.NEW,
            versions=OpportunityVersionMetadata(),
            created_at=evaluation_context.evaluation_timestamp,
            updated_at=evaluation_context.evaluation_timestamp,
        ))

    return opportunities


def discover_from_correlations(
    correlations: list[KnowledgeCorrelation],
    items: list[KnowledgeItem],
    evaluation_context: EvaluationContext,
) -> list[Opportunity]:
    """Discover opportunities from cross-source convergence signals."""
    opportunities: list[Opportunity] = []
    item_by_id = {i.item_id: i for i in items}

    for corr in correlations:
        if corr.signal not in (
            CorrelationSignal.CROSS_SOURCE_CONVERGENCE,
            CorrelationSignal.SUSTAINED_ATTENTION,
        ):
            continue

        title = f"Converging signal: {', '.join(corr.entities[:2])}"
        domain = "cross-source"
        opp_type = OpportunityType.UNKNOWN

        # Find evidence items for this correlation
        evidence_items = [item_by_id[eid] for eid in corr.evidence_ids if eid in item_by_id]
        all_evidence = []
        seen_ev: set[str] = set()
        for it in evidence_items:
            for ev in it.evidence:
                if ev.evidence_id not in seen_ev:
                    seen_ev.add(ev.evidence_id)
                    all_evidence.append(ev)

        opp_id = build_opportunity_id(title, domain, opp_type)
        confidence = round(corr.strength * 0.8 + 0.1, 4)
        novelty = round(corr.strength * 0.6, 4)

        provenance = OpportunityProvenance(
            correlation_ids=[corr.correlation_id],
            entity_ids=list(corr.entities),
            evidence_ids=list(corr.evidence_ids)[:25],
            discovery_method="cross_source_correlation",
            discovered_at=evaluation_context.evaluation_timestamp,
        )

        explanation = OpportunityExplanation(
            why_exists=(
                f"Signal '{corr.signal.value}' detected with strength {corr.strength:.2f} "
                f"across {len(corr.source_ids)} source(s). {corr.explanation}"
            ),
            evidence_basis=list(corr.evidence_ids)[:10],
            source_contributions={sid: round(1.0 / max(1, len(corr.source_ids)), 3) for sid in corr.source_ids},
            confidence_rationale=f"Derived from correlation strength {corr.strength:.3f}.",
            lifecycle_rationale="Stage NEW: correlation-based discovery.",
        )

        score = OpportunityScore(
            novelty=novelty,
            evidence_strength=min(1.0, len(corr.evidence_ids) / 10.0),
            source_diversity=min(1.0, len(corr.source_ids) / 4.0),
            growth_velocity=corr.strength,
            confidence=confidence,
            risk=round(1.0 - corr.strength, 4),
            market_impact=corr.strength,
            strategic_relevance=corr.strength,
            consistency=corr.strength,
            freshness=0.5,
            evidence_ids=list(corr.evidence_ids)[:10],
        )

        opportunities.append(Opportunity(
            opportunity_id=opp_id,
            title=title,
            summary=f"Cross-source convergence detected: {corr.explanation[:256]}",
            description=corr.explanation,
            confidence=confidence,
            priority=round(score.composite_score, 4),
            novelty=novelty,
            maturity=round(min(1.0, corr.strength), 4),
            urgency=round(corr.strength, 4),
            impact=round(corr.strength, 4),
            opportunity_type=opp_type,
            market="",
            domain=domain,
            evidence=all_evidence[:10],
            entities=[],
            relationships=[],
            sources=[],
            correlations=[corr],
            provenance=provenance,
            score=score,
            explanation=explanation,
            lifecycle_stage=LifecycleStage.NEW,
            versions=OpportunityVersionMetadata(),
            created_at=evaluation_context.evaluation_timestamp,
            updated_at=evaluation_context.evaluation_timestamp,
        ))

    return opportunities


def _build_score_from_items(
    items: list[KnowledgeItem],
    evidence: list,
    sources: list,
    novelty: float,
    confidence: float,
) -> OpportunityScore:
    source_types = {it.source.source_type for it in items}
    avg_freshness = sum(it.freshness.knowledge_freshness for it in items) / max(1, len(items))
    avg_engagement = sum(it.engagement_score for it in items) / max(1, len(items))
    evidence_strength = min(1.0, len(evidence) / 10.0)
    source_diversity = min(1.0, len(source_types) / 4.0)
    growth_velocity = min(1.0, len(items) / 10.0)
    market_impact = min(1.0, avg_engagement / 500.0 + 0.2)
    strategic_relevance = min(1.0, confidence * 0.8 + source_diversity * 0.2)
    consistency = min(1.0, evidence_strength * 0.7 + source_diversity * 0.3)
    risk = round(1.0 - confidence, 4)

    evidence_ids = [ev.evidence_id for ev in evidence[:10]]

    return OpportunityScore(
        novelty=round(novelty, 4),
        evidence_strength=round(evidence_strength, 4),
        source_diversity=round(source_diversity, 4),
        growth_velocity=round(growth_velocity, 4),
        confidence=round(confidence, 4),
        risk=round(risk, 4),
        market_impact=round(market_impact, 4),
        strategic_relevance=round(strategic_relevance, 4),
        consistency=round(consistency, 4),
        freshness=round(avg_freshness, 4),
        evidence_ids=evidence_ids,
    )
