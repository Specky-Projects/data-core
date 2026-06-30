"""Research Engine — conducts advisory research."""
from __future__ import annotations

import uuid

from app.capability_orchestrator.contracts import (
    CapabilityKind,
    CapabilityRegistration,
    CapabilityRequest,
    CapabilityResponse,
)
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.research_engine.cache import ResearchCache
from app.research_engine.capabilities.architecture import ArchitectureResearchCapability
from app.research_engine.capabilities.comparative import ComparativeCapability
from app.research_engine.capabilities.competitive import CompetitiveResearchCapability
from app.research_engine.capabilities.opportunity import OpportunityResearchCapability
from app.research_engine.capabilities.scientific import ScientificResearchCapability
from app.research_engine.capabilities.technology_eval import TechnologyEvalCapability
from app.research_engine.capabilities.trend import TrendResearchCapability
from app.research_engine.contracts import ResearchKind
from app.scientific_identity.contract import stable_hash


class ResearchEngine:
    name = "research_engine"

    CAPABILITY_COMPARATIVE = "research.comparative"
    CAPABILITY_ARCHITECTURE = "research.architecture"
    CAPABILITY_TECHNOLOGY = "research.technology"
    CAPABILITY_OPPORTUNITY = "research.opportunity"
    CAPABILITY_COMPETITIVE = "research.competitive"
    CAPABILITY_SCIENTIFIC = "research.scientific"
    CAPABILITY_TREND = "research.trend"

    def __init__(self) -> None:
        self._cache = ResearchCache()
        self._caps_impl = {
            self.CAPABILITY_COMPARATIVE: ComparativeCapability(),
            self.CAPABILITY_ARCHITECTURE: ArchitectureResearchCapability(),
            self.CAPABILITY_TECHNOLOGY: TechnologyEvalCapability(),
            self.CAPABILITY_OPPORTUNITY: OpportunityResearchCapability(),
            self.CAPABILITY_COMPETITIVE: CompetitiveResearchCapability(),
            self.CAPABILITY_SCIENTIFIC: ScientificResearchCapability(),
            self.CAPABILITY_TREND: TrendResearchCapability(),
        }

    def register(self, orchestrator: CapabilityOrchestrator) -> None:
        definitions = [
            (self.CAPABILITY_COMPARATIVE, "Comparative Research"),
            (self.CAPABILITY_ARCHITECTURE, "Architecture Research"),
            (self.CAPABILITY_TECHNOLOGY, "Technology Evaluation"),
            (self.CAPABILITY_OPPORTUNITY, "Opportunity Research"),
            (self.CAPABILITY_COMPETITIVE, "Competitive Research"),
            (self.CAPABILITY_SCIENTIFIC, "Scientific Research"),
            (self.CAPABILITY_TREND, "Trend Research"),
        ]
        for cap_id, name in definitions:
            cap = CapabilityRegistration(
                capability_id=cap_id,
                kind=CapabilityKind.RESEARCH,
                name=name,
                version="1.0.0",
                description=name,
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
            impl = self._caps_impl.get(capability_id)
            result = impl.research(request.inputs) if impl else None
            outputs = {
                "findings": result.findings if result else [],
                "summary": result.summary if result else "",
                "confidence": result.confidence if result else 0.0,
                "cached": result.cached if result else False,
                "advisory_only": True,
            }
            sci_id = stable_hash({"capability": capability_id, "lineage": lineage_id})
            return CapabilityResponse(
                response_id=str(uuid.uuid4()),
                request_id=request.request_id,
                capability_id=capability_id,
                outputs=outputs,
                evidence=result.sources if result else [],
                confidence=result.confidence if result else 0.0,
                advisory_only=True,
                lineage_id=lineage_id,
                scientific_id=sci_id,
            )
        return handler
