"""KnowledgePromoter — promotes candidates to Knowledge."""
from __future__ import annotations

import uuid

from app.knowledge_engine.contracts import Knowledge, KnowledgeCandidate
from app.knowledge_engine.evaluator import KnowledgeCandidateEvaluator
from app.knowledge_engine.graph import KnowledgeGraph
from app.knowledge_engine.memory import ScientificMemory


class KnowledgePromoter:
    def __init__(
        self,
        evaluator: KnowledgeCandidateEvaluator,
        graph: KnowledgeGraph,
        memory: ScientificMemory,
    ) -> None:
        self._evaluator = evaluator
        self._graph = graph
        self._memory = memory

    def try_promote(self, candidate: KnowledgeCandidate) -> Knowledge | None:
        if not self._evaluator.should_promote(candidate):
            self._memory.record("REJECTED", candidate.candidate_id, {
                "reason": "confidence_below_threshold",
                "confidence": candidate.confidence,
            })
            return None
        lineage_id = str(uuid.uuid4())
        knowledge = self._evaluator.promote(candidate, lineage_id)
        self._graph.add(knowledge)
        self._memory.record("PROMOTED", knowledge.knowledge_id, {
            "from_candidate": candidate.candidate_id,
            "confidence": knowledge.confidence,
            "project": knowledge.project,
        })
        return knowledge
