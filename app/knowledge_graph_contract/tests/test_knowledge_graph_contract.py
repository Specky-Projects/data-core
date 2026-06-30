"""Tests for KnowledgeGraphContract — Phase 2.2."""

from app.knowledge_graph_contract.adapter_python import InMemoryKnowledgeGraph
from app.knowledge_graph_contract.contract import (
    KNOWLEDGE_GRAPH_CONTRACT_VERSION,
    KnowledgeEdge,
    KnowledgeEdgeRelation,
    KnowledgeGraphContractProtocol,
    KnowledgeGraphQuery,
    KnowledgeNode,
    KnowledgeNodeType,
)


def _node(node_id: str, label: str = "", node_type: KnowledgeNodeType = KnowledgeNodeType.ENTITY) -> KnowledgeNode:
    return KnowledgeNode(
        node_id=node_id,
        node_type=node_type,
        label=label or node_id,
        payload={"id": node_id},
    )


def _edge(eid: str, src: str, tgt: str, rel: KnowledgeEdgeRelation = KnowledgeEdgeRelation.RELATED_TO) -> KnowledgeEdge:
    return KnowledgeEdge(edge_id=eid, source_node_id=src, target_node_id=tgt, relation=rel)


# ── Contract invariants ────────────────────────────────────────────────────────


def test_node_hash_is_deterministic() -> None:
    n = _node("n1", "BTCUSDT")
    assert n.node_hash == n.node_hash


def test_node_version_is_canonical() -> None:
    n = _node("n1")
    assert n.version == KNOWLEDGE_GRAPH_CONTRACT_VERSION


def test_edge_hash_is_deterministic() -> None:
    e = _edge("e1", "a", "b")
    assert e.edge_hash == e.edge_hash


# ── InMemoryKnowledgeGraph ────────────────────────────────────────────────────


def test_add_node_and_get() -> None:
    g = InMemoryKnowledgeGraph()
    n = _node("node-a", "Alpha")
    g.add_node(n)
    assert g.get_node("node-a") == n
    assert g.node_count() == 1


def test_add_edge_and_neighbors() -> None:
    g = InMemoryKnowledgeGraph()
    g.add_node(_node("a"))
    g.add_node(_node("b"))
    g.add_edge(_edge("e1", "a", "b"))
    assert "b" in g.neighbors("a")
    assert "a" in g.neighbors("b")


def test_get_edges_returns_incident_edges() -> None:
    g = InMemoryKnowledgeGraph()
    g.add_node(_node("x"))
    g.add_node(_node("y"))
    g.add_node(_node("z"))
    g.add_edge(_edge("e-xy", "x", "y"))
    g.add_edge(_edge("e-xz", "x", "z"))
    edges = g.get_edges("x")
    assert len(edges) == 2


def test_edge_count() -> None:
    g = InMemoryKnowledgeGraph()
    g.add_node(_node("p"))
    g.add_node(_node("q"))
    g.add_edge(_edge("e1", "p", "q"))
    assert g.edge_count() == 1


# ── Query ──────────────────────────────────────────────────────────────────────


def test_query_by_node_type() -> None:
    g = InMemoryKnowledgeGraph()
    g.add_node(_node("e1", node_type=KnowledgeNodeType.ENTITY))
    g.add_node(_node("c1", node_type=KnowledgeNodeType.CLAIM))
    g.add_node(_node("c2", node_type=KnowledgeNodeType.CLAIM))
    q = KnowledgeGraphQuery(node_types=(KnowledgeNodeType.CLAIM,))
    result = g.query(q)
    assert len(result.nodes) == 2
    assert all(n.node_type == KnowledgeNodeType.CLAIM for n in result.nodes)


def test_query_by_label_contains() -> None:
    g = InMemoryKnowledgeGraph()
    g.add_node(KnowledgeNode(node_id="b1", node_type=KnowledgeNodeType.ENTITY, label="Bitcoin Signal", payload={}))
    g.add_node(KnowledgeNode(node_id="e1", node_type=KnowledgeNodeType.ENTITY, label="Ethereum Volume", payload={}))
    q = KnowledgeGraphQuery(label_contains="bitcoin")
    result = g.query(q)
    assert len(result.nodes) == 1
    assert result.nodes[0].node_id == "b1"


def test_query_bfs_respects_max_depth() -> None:
    g = InMemoryKnowledgeGraph()
    for i in range(5):
        g.add_node(_node(f"n{i}"))
    for i in range(4):
        g.add_edge(_edge(f"e{i}", f"n{i}", f"n{i+1}"))

    q = KnowledgeGraphQuery(root_node_id="n0", max_depth=2)
    result = g.query(q)
    node_ids = {n.node_id for n in result.nodes}
    assert "n0" in node_ids
    assert "n1" in node_ids
    assert "n2" in node_ids
    assert "n3" not in node_ids


def test_query_result_hash_is_stable() -> None:
    g = InMemoryKnowledgeGraph()
    g.add_node(_node("a"))
    g.add_node(_node("b"))
    g.add_edge(_edge("e1", "a", "b"))
    q = KnowledgeGraphQuery()
    r1 = g.query(q)
    r2 = g.query(q)
    assert r1.result_hash == r2.result_hash


# ── Snapshot ───────────────────────────────────────────────────────────────────


def test_snapshot_captures_state() -> None:
    g = InMemoryKnowledgeGraph()
    g.add_node(_node("n1"))
    g.add_node(_node("n2"))
    snap = g.snapshot("2026-06-30T00:00:00")
    assert snap.node_count == 2
    assert snap.edge_count == 0
    assert snap.version == KNOWLEDGE_GRAPH_CONTRACT_VERSION
    assert snap.graph_hash


def test_snapshot_hash_changes_after_adding_node() -> None:
    g = InMemoryKnowledgeGraph()
    snap1 = g.snapshot("2026-06-30T00:00:00")
    g.add_node(_node("n-new"))
    snap2 = g.snapshot("2026-06-30T00:00:01")
    assert snap1.graph_hash != snap2.graph_hash


# ── Protocol compliance ────────────────────────────────────────────────────────


def test_in_memory_graph_satisfies_protocol() -> None:
    g = InMemoryKnowledgeGraph()
    assert isinstance(g, KnowledgeGraphContractProtocol)


# ── All nodes/edges ────────────────────────────────────────────────────────────


def test_all_nodes_and_edges() -> None:
    g = InMemoryKnowledgeGraph()
    g.add_node(_node("x"))
    g.add_node(_node("y"))
    g.add_edge(_edge("exy", "x", "y"))
    assert len(g.all_nodes()) == 2
    assert len(g.all_edges()) == 1
