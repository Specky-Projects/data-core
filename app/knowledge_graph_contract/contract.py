"""KnowledgeGraphContract — canonical schema for nodes, edges, queries, snapshots.

This contract defines structure only — no domain rules.
All domain behaviour stays in the implementing adapters.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


KNOWLEDGE_GRAPH_CONTRACT_VERSION = "knowledge-graph-contract-v1"


# ── Utilities ─────────────────────────────────────────────────────────────────


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _normalize(value[k]) for k in sorted(value)}
    if isinstance(value, list | tuple):
        return [_normalize(item) for item in value]
    return value


def stable_json(value: Any) -> str:
    return json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_hash(value: Any, length: int = 32) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:length]


# ── Enumerations ──────────────────────────────────────────────────────────────


class KnowledgeNodeType(StrEnum):
    """Domain-agnostic node types."""

    ENTITY = "ENTITY"
    CLAIM = "CLAIM"
    EVIDENCE = "EVIDENCE"
    EXPERIMENT = "EXPERIMENT"
    CAPABILITY = "CAPABILITY"
    REVIEWER = "REVIEWER"
    REPLAY = "REPLAY"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    GATE = "GATE"
    GENERIC = "GENERIC"


class KnowledgeEdgeRelation(StrEnum):
    """Canonical relation taxonomy."""

    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    PRODUCES = "PRODUCES"
    VALIDATES = "VALIDATES"
    CAUSES = "CAUSES"
    CORRELATES = "CORRELATES"
    DERIVED_FROM = "DERIVED_FROM"
    DEPENDS_ON = "DEPENDS_ON"
    RELATED_TO = "RELATED_TO"


# ── Structural types ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class KnowledgeNode:
    """An immutable node in the knowledge graph."""

    node_id: str
    node_type: KnowledgeNodeType
    label: str
    payload: dict[str, Any]
    version: str = KNOWLEDGE_GRAPH_CONTRACT_VERSION
    scientific_identity_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def node_hash(self) -> str:
        return stable_hash(
            {"node_id": self.node_id, "label": self.label, "payload": self.payload}
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class KnowledgeEdge:
    """An immutable directed edge between two nodes."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    relation: KnowledgeEdgeRelation
    weight: float = 1.0
    version: str = KNOWLEDGE_GRAPH_CONTRACT_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def edge_hash(self) -> str:
        return stable_hash(
            {
                "source": self.source_node_id,
                "target": self.target_node_id,
                "relation": str(self.relation),
            }
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Query types ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class KnowledgeGraphQuery:
    """A declarative query against the knowledge graph."""

    node_types: tuple[KnowledgeNodeType, ...] = ()
    relations: tuple[KnowledgeEdgeRelation, ...] = ()
    max_depth: int = 3
    root_node_id: str | None = None
    label_contains: str | None = None
    scientific_identity_id: str | None = None


@dataclass(frozen=True)
class KnowledgeGraphQueryResult:
    nodes: tuple[KnowledgeNode, ...]
    edges: tuple[KnowledgeEdge, ...]
    query: KnowledgeGraphQuery

    @property
    def result_hash(self) -> str:
        return stable_hash(
            {
                "nodes": [n.node_id for n in self.nodes],
                "edges": [e.edge_id for e in self.edges],
            }
        )


# ── Snapshot ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class KnowledgeGraphSnapshot:
    """Immutable point-in-time snapshot of a knowledge graph."""

    snapshot_id: str
    captured_at: str
    node_count: int
    edge_count: int
    graph_hash: str
    version: str = KNOWLEDGE_GRAPH_CONTRACT_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Protocol ──────────────────────────────────────────────────────────────────


@runtime_checkable
class KnowledgeGraphContractProtocol(Protocol):
    """Contract that all knowledge graph implementations must satisfy.

    No domain rules here — only structural operations.
    """

    def add_node(self, node: KnowledgeNode) -> None: ...

    def add_edge(self, edge: KnowledgeEdge) -> None: ...

    def get_node(self, node_id: str) -> KnowledgeNode | None: ...

    def get_edges(self, node_id: str) -> list[KnowledgeEdge]: ...

    def neighbors(self, node_id: str) -> list[str]: ...

    def query(self, q: KnowledgeGraphQuery) -> KnowledgeGraphQueryResult: ...

    def node_count(self) -> int: ...

    def edge_count(self) -> int: ...

    def snapshot(self, captured_at: str) -> KnowledgeGraphSnapshot: ...

    def all_nodes(self) -> list[KnowledgeNode]: ...

    def all_edges(self) -> list[KnowledgeEdge]: ...
