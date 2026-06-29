"""Knowledge Fusion — Stage 5.

Merges knowledge from independent sources into richer unified representations.
Duplicate discoveries converge into one canonical representation.
All merging is deterministic — no wall-clock.
"""

from __future__ import annotations

from app.knowledge.dto import (
    FusedKnowledgeItem,
    FusionStrategy,
    KnowledgeItem,
    KnowledgeVersionMetadata,
    _k_stable_hash,
)
from app.knowledge.entity_resolution import merge_entity_lists


def _topic_overlap(a: KnowledgeItem, b: KnowledgeItem) -> float:
    set_a = set(a.topics)
    set_b = set(b.topics)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _entity_overlap(a: KnowledgeItem, b: KnowledgeItem) -> float:
    ids_a = {e.entity_id for e in a.entities}
    ids_b = {e.entity_id for e in b.entities}
    if not ids_a or not ids_b:
        return 0.0
    return len(ids_a & ids_b) / len(ids_a | ids_b)


def _url_canonical(a: KnowledgeItem, b: KnowledgeItem) -> bool:
    """True if both items share the same canonical URL (excluding query params)."""
    def _base(url: str) -> str:
        return url.split("?")[0].rstrip("/").lower()
    return bool(a.url and b.url and _base(a.url) == _base(b.url))


def _are_fusible(a: KnowledgeItem, b: KnowledgeItem, threshold: float = 0.3) -> tuple[bool, FusionStrategy]:
    if _url_canonical(a, b):
        return True, FusionStrategy.URL_CANONICAL
    entity_sim = _entity_overlap(a, b)
    if entity_sim >= threshold:
        return True, FusionStrategy.ENTITY_OVERLAP
    topic_sim = _topic_overlap(a, b)
    if topic_sim >= threshold:
        return True, FusionStrategy.TOPIC_OVERLAP
    return False, FusionStrategy.ENTITY_OVERLAP


def fuse_knowledge_items(items: list[KnowledgeItem], threshold: float = 0.3) -> list[FusedKnowledgeItem]:
    """Group and fuse knowledge items from different sources into FusedKnowledgeItem list."""
    if not items:
        return []

    # Build fusion groups using union-find
    n = len(items)
    parent = list(range(n))
    strategy_map: dict[tuple[int, int], FusionStrategy] = {}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    for i in range(n):
        for j in range(i + 1, n):
            if items[i].source.source_id != items[j].source.source_id:
                fusible, strategy = _are_fusible(items[i], items[j], threshold)
                if fusible:
                    strategy_map[(min(i, j), max(i, j))] = strategy
                    union(i, j)

    groups: dict[int, list[int]] = {}
    for idx in range(n):
        root = find(idx)
        groups.setdefault(root, []).append(idx)

    fused: list[FusedKnowledgeItem] = []
    for root, members in groups.items():
        if len(members) == 1:
            idx = members[0]
            item = items[idx]
            fused.append(FusedKnowledgeItem(
                fusion_id=_k_stable_hash({"single": item.item_id}),
                primary_item=item,
                contributing_items=[],
                merged_entities=list(item.entities),
                merged_evidence=list(item.evidence),
                merged_topics=list(item.topics),
                source_count=1,
                fusion_strategy=FusionStrategy.ENTITY_OVERLAP,
                confidence=item.confidence,
            ))
        else:
            group_items = [items[i] for i in members]
            primary = max(group_items, key=lambda it: it.engagement_score + it.confidence)
            contributing = [it for it in group_items if it.item_id != primary.item_id]

            merged_entities = merge_entity_lists([it.entities for it in group_items])
            merged_evidence_ids: set[str] = set()
            merged_evidence = []
            for it in group_items:
                for ev in it.evidence:
                    if ev.evidence_id not in merged_evidence_ids:
                        merged_evidence_ids.add(ev.evidence_id)
                        merged_evidence.append(ev)
            merged_topics = sorted({t for it in group_items for t in it.topics})

            pair_strategy = strategy_map.get((members[0], members[-1]), FusionStrategy.ENTITY_OVERLAP)
            confidence = min(1.0, sum(it.confidence for it in group_items) / len(group_items))

            fused.append(FusedKnowledgeItem(
                fusion_id=_k_stable_hash({"ids": sorted(it.item_id for it in group_items)}),
                primary_item=primary,
                contributing_items=contributing,
                merged_entities=merged_entities,
                merged_evidence=merged_evidence[:25],
                merged_topics=merged_topics,
                source_count=len({it.source.source_id for it in group_items}),
                fusion_strategy=pair_strategy,
                confidence=round(confidence, 4),
            ))

    return fused
