"""Knowledge Engine — transforms observations into promoted Knowledge."""
from __future__ import annotations

import uuid

from app.capability_orchestrator.contracts import (
    CapabilityKind,
    CapabilityRegistration,
    CapabilityRequest,
    CapabilityResponse,
)
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.knowledge_engine.contracts import KnowledgeCandidate, KnowledgeScope
from app.knowledge_engine.demoter import KnowledgeDemoter
from app.knowledge_engine.evaluator import KnowledgeCandidateEvaluator
from app.knowledge_engine.factory import TruthCandidateFactory
from app.knowledge_engine.graph import KnowledgeGraph
from app.knowledge_engine.memory import ScientificMemory
from app.knowledge_engine.promoter import KnowledgePromoter
from app.scientific_identity.contract import stable_hash


class KnowledgeEngine:
    name = "knowledge_engine"

    CAPABILITY_INGEST = "knowledge.ingest"
    CAPABILITY_QUERY = "knowledge.query"
    CAPABILITY_DEMOTE = "knowledge.demote"
    CAPABILITY_STATS = "knowledge.stats"

    def __init__(self) -> None:
        self._memory = ScientificMemory()
        self._graph = KnowledgeGraph()
        self._evaluator = KnowledgeCandidateEvaluator()
        self._factory = TruthCandidateFactory()
        self._promoter = KnowledgePromoter(self._evaluator, self._graph, self._memory)
        self._demoter = KnowledgeDemoter(self._graph, self._memory)

    def register(self, orchestrator: CapabilityOrchestrator) -> None:
        caps_defs = [
            (self.CAPABILITY_INGEST, "Ingest Observations", "Processes observations into knowledge"),
            (self.CAPABILITY_QUERY, "Query Knowledge", "Queries the knowledge graph"),
            (self.CAPABILITY_DEMOTE, "Demote Knowledge", "Marks knowledge as demoted"),
            (self.CAPABILITY_STATS, "Knowledge Stats", "Returns knowledge graph statistics"),
        ]
        for cap_id, name, description in caps_defs:
            cap = CapabilityRegistration(
                capability_id=cap_id,
                kind=CapabilityKind.KNOWLEDGE,
                name=name,
                version="1.0.0",
                description=description,
                input_schema={},
                output_schema={},
                dependencies=[],
                advisory_only=True,
                owner=self.name,
            )
            orchestrator.registry.register(cap)
            orchestrator.register_handler(cap_id, self._dispatch(cap_id))

    def _dispatch(self, capability_id: str):
        def handler(request: CapabilityRequest) -> CapabilityResponse:
            lineage_id = str(uuid.uuid4())
            outputs = self._handle(capability_id, request)
            sci_id = stable_hash({"capability": capability_id, "lineage": lineage_id})
            return CapabilityResponse(
                response_id=str(uuid.uuid4()),
                request_id=request.request_id,
                capability_id=capability_id,
                outputs=outputs,
                evidence=[],
                confidence=0.9,
                advisory_only=True,
                lineage_id=lineage_id,
                scientific_id=sci_id,
            )
        return handler

    def _handle(self, capability_id: str, request: CapabilityRequest) -> dict:
        if capability_id == self.CAPABILITY_INGEST:
            observations = request.inputs.get("observations", [])
            promoted = []
            rejected = []
            for obs in observations:
                truth = self._factory.from_observation_dict(obs)
                candidate = KnowledgeCandidate(
                    candidate_id=truth.candidate_id,
                    truth_candidate_id=truth.candidate_id,
                    title=f"Knowledge: {truth.proposition[:50]}",
                    proposition=truth.proposition,
                    domain=truth.domain,
                    project=truth.project,
                    scope=KnowledgeScope.PROJECT,
                    evidence=truth.evidence,
                    confidence=truth.confidence,
                    advisory_only=True,
                )
                knowledge = self._promoter.try_promote(candidate)
                if knowledge:
                    promoted.append(knowledge.knowledge_id)
                else:
                    rejected.append(candidate.candidate_id)
            return {
                "promoted": promoted,
                "rejected": rejected,
                "total_in_graph": self._graph.count(),
                "advisory_only": True,
            }

        elif capability_id == self.CAPABILITY_QUERY:
            project = request.inputs.get("project")
            domain = request.inputs.get("domain")
            if project:
                results = self._graph.by_project(project)
            elif domain:
                results = self._graph.by_domain(domain)
            else:
                results = self._graph.all()
            return {
                "knowledge": [
                    {
                        "knowledge_id": k.knowledge_id,
                        "title": k.title,
                        "proposition": k.proposition,
                        "confidence": k.confidence,
                        "status": str(k.status),
                        "project": k.project,
                    }
                    for k in results
                ],
                "count": len(results),
                "advisory_only": True,
            }

        elif capability_id == self.CAPABILITY_DEMOTE:
            knowledge_id = request.inputs.get("knowledge_id", "")
            reason = request.inputs.get("reason", "no reason given")
            success = self._demoter.demote(knowledge_id, reason)
            return {"demoted": success, "knowledge_id": knowledge_id, "advisory_only": True}

        elif capability_id == self.CAPABILITY_STATS:
            return {
                "total_knowledge": self._graph.count(),
                "total_events": self._memory.count(),
                "advisory_only": True,
            }

        return {"advisory_only": True}
