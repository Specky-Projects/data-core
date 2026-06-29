"""Cross-Source Correlation — Stage 6.

Identifies meaningful relationships between independent sources.
Every correlation exposes evidence. All computations are deterministic.
No wall-clock dependency — evaluation_context.evaluation_timestamp is the reference.
"""

from __future__ import annotations

from collections import defaultdict

from app.adaptive_intelligence.dto import EvaluationContext
from app.knowledge.dto import (
    CorrelationSignal,
    KnowledgeCorrelation,
    KnowledgeItem,
    KnowledgeVersionMetadata,
    build_correlation_id,
)


def _items_in_window(items: list[KnowledgeItem], window_days: int, evaluation_context: EvaluationContext) -> list[KnowledgeItem]:
    ref_ts = evaluation_context.evaluation_timestamp.timestamp()
    cutoff = ref_ts - window_days * 86_400.0
    return [
        it for it in items
        if it.published_at is not None and it.published_at.timestamp() >= cutoff
    ]


def compute_cross_source_correlations(
    items: list[KnowledgeItem],
    evaluation_context: EvaluationContext,
    window_days: int = 30,
    min_sources: int = 2,
    min_mentions: int = 2,
) -> list[KnowledgeCorrelation]:
    """Detect entities co-occurring across multiple sources within a time window."""
    windowed = _items_in_window(items, window_days, evaluation_context)
    if not windowed:
        return []

    # entity_id → {source_id → [evidence_ids]}
    entity_source_evidence: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    for item in windowed:
        for entity in item.entities:
            entity_source_evidence[entity.entity_id][item.source.source_id].extend(
                [e.evidence_id for e in item.evidence[:5]]
            )

    correlations: list[KnowledgeCorrelation] = []
    for entity_id, source_map in entity_source_evidence.items():
        source_count = len(source_map)
        total_mentions = sum(len(ev) for ev in source_map.values())

        if source_count < min_sources or total_mentions < min_mentions:
            continue

        all_evidence = sorted({eid for evs in source_map.values() for eid in evs})[:10]
        source_ids = sorted(source_map.keys())

        # Classify the signal
        if source_count >= 3:
            signal = CorrelationSignal.CROSS_SOURCE_CONVERGENCE
        elif total_mentions >= 5:
            signal = CorrelationSignal.SUSTAINED_ATTENTION
        else:
            signal = CorrelationSignal.INCREASING_MENTIONS

        strength = min(1.0, (source_count / 4.0) * 0.5 + (total_mentions / 10.0) * 0.5)

        # Build explanation from evidence
        explanation = (
            f"Entity appears across {source_count} source(s) with {total_mentions} mention(s) "
            f"within a {window_days}-day window. Sources: {', '.join(source_ids)}."
        )

        correlations.append(KnowledgeCorrelation(
            correlation_id=build_correlation_id([entity_id], signal, window_days),
            entities=[entity_id],
            signal=signal,
            strength=round(strength, 4),
            evidence_ids=all_evidence,
            source_ids=source_ids,
            explanation=explanation,
            window_days=window_days,
        ))

    return sorted(correlations, key=lambda c: -c.strength)


def compute_entity_co_occurrence(
    items: list[KnowledgeItem],
    evaluation_context: EvaluationContext,
    window_days: int = 30,
    min_co_occurrence: int = 2,
) -> list[KnowledgeCorrelation]:
    """Detect pairs of entities frequently co-occurring across items."""
    windowed = _items_in_window(items, window_days, evaluation_context)
    if not windowed:
        return []

    # (entity_a, entity_b) → [(source_id, evidence_ids)]
    pair_occurrences: dict[tuple[str, str], list[tuple[str, list[str]]]] = defaultdict(list)

    for item in windowed:
        entity_ids = sorted({e.entity_id for e in item.entities})
        evidence_ids = [e.evidence_id for e in item.evidence[:3]]
        for i, eid_a in enumerate(entity_ids):
            for eid_b in entity_ids[i + 1:]:
                pair_occurrences[(eid_a, eid_b)].append((item.source.source_id, evidence_ids))

    correlations: list[KnowledgeCorrelation] = []
    for (eid_a, eid_b), occurrences in pair_occurrences.items():
        if len(occurrences) < min_co_occurrence:
            continue

        all_sources = sorted({occ[0] for occ in occurrences})
        all_evidence = sorted({eid for _, evs in occurrences for eid in evs})[:10]
        strength = min(1.0, len(occurrences) / 10.0)

        correlations.append(KnowledgeCorrelation(
            correlation_id=build_correlation_id([eid_a, eid_b], CorrelationSignal.CO_OCCURS_WITH if hasattr(CorrelationSignal, "CO_OCCURS_WITH") else CorrelationSignal.RELATED_TO, window_days),
            entities=[eid_a, eid_b],
            signal=CorrelationSignal.INCREASING_MENTIONS,
            strength=round(strength, 4),
            evidence_ids=all_evidence,
            source_ids=all_sources,
            explanation=f"Entities co-occur {len(occurrences)} time(s) in {len(all_sources)} source(s) within {window_days} days.",
            window_days=window_days,
        ))

    return sorted(correlations, key=lambda c: -c.strength)
