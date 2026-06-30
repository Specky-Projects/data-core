"""KnowledgeCandidateEvaluator — filters candidates by confidence threshold."""
from __future__ import annotations

import uuid

from app.knowledge_engine.contracts import Knowledge, KnowledgeCandidate, KnowledgeScope, KnowledgeStatus
from app.scientific_identity.contract import stable_hash

PROMOTION_THRESHOLD = 0.6


class KnowledgeCandidateEvaluator:
    def __init__(self, threshold: float = PROMOTION_THRESHOLD) -> None:
        self.threshold = threshold

    def should_promote(self, candidate: KnowledgeCandidate) -> bool:
        return candidate.confidence >= self.threshold

    def promote(self, candidate: KnowledgeCandidate, lineage_id: str) -> Knowledge:
        """Promote a KnowledgeCandidate to Knowledge."""
        assert candidate.evidence, "Cannot promote candidate without evidence"
        knowledge_id = stable_hash({
            "candidate": candidate.candidate_id,
            "lineage": lineage_id,
        })
        sci_id = stable_hash({"knowledge_id": knowledge_id, "producer": "knowledge_engine"})
        return Knowledge(
            knowledge_id=knowledge_id,
            scientific_id=sci_id,
            lineage_id=lineage_id,
            title=candidate.title,
            proposition=candidate.proposition,
            domain=candidate.domain,
            project=candidate.project,
            scope=candidate.scope,
            evidence=candidate.evidence,
            confidence=candidate.confidence,
            version_number=1,
            status=KnowledgeStatus.ACTIVE,
        )
