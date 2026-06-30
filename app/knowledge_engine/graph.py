"""KnowledgeGraph — in-memory graph of promoted Knowledge."""
from __future__ import annotations

from app.knowledge_engine.contracts import Knowledge, KnowledgeScope


class KnowledgeGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, Knowledge] = {}

    def add(self, knowledge: Knowledge) -> None:
        self._nodes[knowledge.knowledge_id] = knowledge

    def get(self, knowledge_id: str) -> Knowledge | None:
        return self._nodes.get(knowledge_id)

    def by_project(self, project: str) -> list[Knowledge]:
        return [k for k in self._nodes.values() if k.project == project]

    def by_domain(self, domain: str) -> list[Knowledge]:
        return [k for k in self._nodes.values() if k.domain == domain]

    def by_scope(self, scope: KnowledgeScope) -> list[Knowledge]:
        return [k for k in self._nodes.values() if k.scope == scope]

    def all(self) -> list[Knowledge]:
        return list(self._nodes.values())

    def count(self) -> int:
        return len(self._nodes)
