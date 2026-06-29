"""Logical Knowledge Graph — Stage 10.

Implements ONLY the logical model. No graph DB. No Neo4j. No Gremlin.
Relationships are pure Python DTOs. Future versions may materialize the graph.
"""

from __future__ import annotations

from collections import defaultdict

from app.knowledge.dto import (
    KnowledgeEntity,
    KnowledgeItem,
    KnowledgeRelationship,
    KnowledgeVersionMetadata,
    RelationshipType,
    build_relationship_id,
)


class LogicalKnowledgeGraph:
    """In-memory logical graph. Adjacency list over entity IDs."""

    def __init__(self) -> None:
        self._entities: dict[str, KnowledgeEntity] = {}
        self._relationships: dict[str, KnowledgeRelationship] = {}
        self._adjacency: dict[str, set[str]] = defaultdict(set)

    def add_entity(self, entity: KnowledgeEntity) -> None:
        self._entities[entity.entity_id] = entity
        if entity.entity_id not in self._adjacency:
            self._adjacency[entity.entity_id] = set()

    def add_relationship(self, rel: KnowledgeRelationship) -> None:
        self._relationships[rel.relationship_id] = rel
        self._adjacency[rel.source_entity_id].add(rel.target_entity_id)
        self._adjacency[rel.target_entity_id].add(rel.source_entity_id)

    def neighbors(self, entity_id: str) -> list[str]:
        return sorted(self._adjacency.get(entity_id, set()))

    def entity_count(self) -> int:
        return len(self._entities)

    def relationship_count(self) -> int:
        return len(self._relationships)

    def get_entity(self, entity_id: str) -> KnowledgeEntity | None:
        return self._entities.get(entity_id)

    def get_relationships(self, entity_id: str) -> list[KnowledgeRelationship]:
        return [
            rel for rel in self._relationships.values()
            if rel.source_entity_id == entity_id or rel.target_entity_id == entity_id
        ]

    def all_relationships(self) -> list[KnowledgeRelationship]:
        return list(self._relationships.values())

    def all_entities(self) -> list[KnowledgeEntity]:
        return list(self._entities.values())


def build_knowledge_graph(
    items: list[KnowledgeItem],
) -> LogicalKnowledgeGraph:
    """Build the logical knowledge graph from a list of KnowledgeItems.

    Relationships are derived from entity co-occurrence within items.
    Strength is proportional to co-occurrence frequency.
    """
    graph = LogicalKnowledgeGraph()
    entity_map: dict[str, KnowledgeEntity] = {}
    co_occurrence: dict[tuple[str, str], list[str]] = defaultdict(list)

    for item in items:
        for entity in item.entities:
            if entity.entity_id not in entity_map:
                entity_map[entity.entity_id] = entity
            entity_ids = sorted({e.entity_id for e in item.entities})
            evidence_ids = [e.evidence_id for e in item.evidence[:3]]
            for i, eid_a in enumerate(entity_ids):
                for eid_b in entity_ids[i + 1:]:
                    co_occurrence[(eid_a, eid_b)].extend(evidence_ids)

    for entity in entity_map.values():
        graph.add_entity(entity)

    for (eid_a, eid_b), evidence_ids in co_occurrence.items():
        strength = min(1.0, len(evidence_ids) / 5.0)
        rel_id = build_relationship_id(eid_a, eid_b, RelationshipType.CO_OCCURS_WITH)
        rel = KnowledgeRelationship(
            relationship_id=rel_id,
            source_entity_id=eid_a,
            target_entity_id=eid_b,
            relationship_type=RelationshipType.CO_OCCURS_WITH,
            strength=round(strength, 4),
            evidence_ids=sorted(set(evidence_ids))[:10],
            co_occurrence_count=len(evidence_ids),
            source_ids=[],
        )
        graph.add_relationship(rel)

    return graph
