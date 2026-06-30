"""KnowledgeDemoter — marks Knowledge as DEMOTED (does not delete)."""
from __future__ import annotations

from app.knowledge_engine.contracts import Knowledge, KnowledgeStatus
from app.knowledge_engine.graph import KnowledgeGraph
from app.knowledge_engine.memory import ScientificMemory


class KnowledgeDemoter:
    def __init__(self, graph: KnowledgeGraph, memory: ScientificMemory) -> None:
        self._graph = graph
        self._memory = memory

    def demote(self, knowledge_id: str, reason: str) -> bool:
        knowledge = self._graph.get(knowledge_id)
        if knowledge is None:
            return False
        # Knowledge is frozen (dataclass) — we replace it in the graph with a new status
        import dataclasses
        demoted = dataclasses.replace(knowledge, status=KnowledgeStatus.DEMOTED)
        self._graph._nodes[knowledge_id] = demoted
        self._memory.record("DEMOTED", knowledge_id, {"reason": reason})
        return True
