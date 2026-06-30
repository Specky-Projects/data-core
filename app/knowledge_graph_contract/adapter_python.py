"""PythonKnowledgeGraphAdapter — bridges LogicalKnowledgeGraph to KnowledgeGraphContract.

LogicalKnowledgeGraph is not modified.
This adapter wraps it and exposes the canonical contract protocol.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from app.knowledge_graph_contract.contract import (
    KNOWLEDGE_GRAPH_CONTRACT_VERSION,
    KnowledgeEdge,
    KnowledgeEdgeRelation,
    KnowledgeGraphContractProtocol,
    KnowledgeGraphQuery,
    KnowledgeGraphQueryResult,
    KnowledgeGraphSnapshot,
    KnowledgeNode,
    KnowledgeNodeType,
    stable_hash,
)


class InMemoryKnowledgeGraph:
    """Canonical in-memory implementation of KnowledgeGraphContractProtocol.

    Self-contained — does not depend on LogicalKnowledgeGraph so it can
    be used independently in tests and new code paths.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, KnowledgeNode] = {}
        self._edges: dict[str, KnowledgeEdge] = {}
        self._adjacency: dict[str, set[str]] = defaultdict(set)
        self._edges_by_node: dict[str, list[str]] = defaultdict(list)

    def add_node(self, node: KnowledgeNode) -> None:
        self._nodes[node.node_id] = node
        if node.node_id not in self._adjacency:
            self._adjacency[node.node_id] = set()

    def add_edge(self, edge: KnowledgeEdge) -> None:
        self._edges[edge.edge_id] = edge
        self._adjacency[edge.source_node_id].add(edge.target_node_id)
        self._adjacency[edge.target_node_id].add(edge.source_node_id)
        self._edges_by_node[edge.source_node_id].append(edge.edge_id)
        self._edges_by_node[edge.target_node_id].append(edge.edge_id)

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        return self._nodes.get(node_id)

    def get_edges(self, node_id: str) -> list[KnowledgeEdge]:
        edge_ids = self._edges_by_node.get(node_id, [])
        return [self._edges[eid] for eid in edge_ids if eid in self._edges]

    def neighbors(self, node_id: str) -> list[str]:
        return sorted(self._adjacency.get(node_id, set()))

    def query(self, q: KnowledgeGraphQuery) -> KnowledgeGraphQueryResult:
        nodes = list(self._nodes.values())
        edges = list(self._edges.values())

        if q.node_types:
            nodes = [n for n in nodes if n.node_type in q.node_types]
        if q.label_contains:
            nodes = [n for n in nodes if q.label_contains.lower() in n.label.lower()]
        if q.scientific_identity_id:
            nodes = [n for n in nodes if n.scientific_identity_id == q.scientific_identity_id]

        visible_ids = {n.node_id for n in nodes}

        if q.root_node_id and q.max_depth > 0:
            visible_ids = self._bfs(q.root_node_id, q.max_depth)
            nodes = [n for n in nodes if n.node_id in visible_ids]

        if q.relations:
            edges = [e for e in edges if e.relation in q.relations]
        edges = [e for e in edges if e.source_node_id in visible_ids and e.target_node_id in visible_ids]

        return KnowledgeGraphQueryResult(
            nodes=tuple(nodes),
            edges=tuple(edges),
            query=q,
        )

    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return len(self._edges)

    def snapshot(self, captured_at: str | None = None) -> KnowledgeGraphSnapshot:
        if captured_at is None:
            captured_at = datetime.now(tz=timezone.utc).isoformat()
        graph_hash = stable_hash(
            {
                "nodes": sorted(self._nodes),
                "edges": sorted(self._edges),
            }
        )
        return KnowledgeGraphSnapshot(
            snapshot_id=stable_hash({"graph_hash": graph_hash, "captured_at": captured_at}),
            captured_at=captured_at,
            node_count=self.node_count(),
            edge_count=self.edge_count(),
            graph_hash=graph_hash,
            version=KNOWLEDGE_GRAPH_CONTRACT_VERSION,
        )

    def all_nodes(self) -> list[KnowledgeNode]:
        return list(self._nodes.values())

    def all_edges(self) -> list[KnowledgeEdge]:
        return list(self._edges.values())

    def _bfs(self, root: str, max_depth: int) -> set[str]:
        visited: set[str] = {root}
        frontier = {root}
        for _ in range(max_depth):
            next_frontier: set[str] = set()
            for node_id in frontier:
                for neighbor in self._adjacency.get(node_id, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.add(neighbor)
            frontier = next_frontier
            if not frontier:
                break
        return visited


# ── Adapter from LogicalKnowledgeGraph ────────────────────────────────────────


def adapt_logical_knowledge_graph(logical_graph: object) -> InMemoryKnowledgeGraph:
    """Adapt an existing LogicalKnowledgeGraph to the canonical contract.

    Reads all entities and relationships from the legacy graph and
    re-exposes them through the canonical protocol.
    LogicalKnowledgeGraph is not modified.
    """
    canonical = InMemoryKnowledgeGraph()

    for entity in logical_graph.all_entities():  # type: ignore[attr-defined]
        node = KnowledgeNode(
            node_id=entity.entity_id,
            node_type=KnowledgeNodeType.ENTITY,
            label=entity.canonical_name,
            payload={
                "entity_type": str(entity.entity_type),
                "confidence": getattr(entity, "confidence", 1.0),
                "aliases": list(getattr(entity, "aliases", [])),
            },
            metadata={"source": "logical_knowledge_graph"},
        )
        canonical.add_node(node)

    for rel in logical_graph.all_relationships():  # type: ignore[attr-defined]
        relation = _map_relationship_type(str(rel.relationship_type))
        edge = KnowledgeEdge(
            edge_id=rel.relationship_id,
            source_node_id=rel.source_entity_id,
            target_node_id=rel.target_entity_id,
            relation=relation,
            weight=getattr(rel, "weight", 1.0),
            metadata={"source": "logical_knowledge_graph"},
        )
        canonical.add_edge(edge)

    return canonical


def _map_relationship_type(rel_type: str) -> KnowledgeEdgeRelation:
    mapping = {
        "mentions": KnowledgeEdgeRelation.RELATED_TO,
        "discusses": KnowledgeEdgeRelation.RELATED_TO,
        "compares": KnowledgeEdgeRelation.CORRELATES,
        "implements": KnowledgeEdgeRelation.DERIVED_FROM,
        "depends_on": KnowledgeEdgeRelation.DEPENDS_ON,
        "related_to": KnowledgeEdgeRelation.RELATED_TO,
        "co_occurs_with": KnowledgeEdgeRelation.CORRELATES,
    }
    return mapping.get(rel_type.lower(), KnowledgeEdgeRelation.RELATED_TO)
