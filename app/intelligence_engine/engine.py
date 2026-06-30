"""Intelligence Engine — runs AI analysis via specialists."""
from __future__ import annotations

import uuid

from app.capability_orchestrator.contracts import (
    CapabilityKind,
    CapabilityRegistration,
    CapabilityRequest,
    CapabilityResponse,
)
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.intelligence_engine.contracts import AISpecialistKind, IntelligenceRequest
from app.intelligence_engine.router import IntelligenceRouter
from app.scientific_identity.contract import stable_hash


class IntelligenceEngine:
    name = "intelligence_engine"

    CAPABILITY_ANALYZE = "intelligence.analyze"
    CAPABILITY_DIAGNOSE = "intelligence.diagnose"
    CAPABILITY_ARCHITECTURE = "intelligence.architecture"

    def __init__(self) -> None:
        self._router = IntelligenceRouter()

    def register(self, orchestrator: CapabilityOrchestrator) -> None:
        caps = [
            CapabilityRegistration(
                capability_id=self.CAPABILITY_ANALYZE,
                kind=CapabilityKind.INTELLIGENCE,
                name="Analyze",
                version="1.0.0",
                description="Routes analysis to appropriate AI specialist",
                input_schema={"specialist_kind": "str", "observations": "list"},
                output_schema={"analysis": "dict", "confidence": "float"},
                dependencies=[],
                advisory_only=True,
                owner=self.name,
            ),
            CapabilityRegistration(
                capability_id=self.CAPABILITY_DIAGNOSE,
                kind=CapabilityKind.INTELLIGENCE,
                name="Diagnose",
                version="1.0.0",
                description="Root cause diagnosis",
                input_schema={"observations": "list"},
                output_schema={"root_cause": "str", "factors": "list"},
                dependencies=[],
                advisory_only=True,
                owner=self.name,
            ),
            CapabilityRegistration(
                capability_id=self.CAPABILITY_ARCHITECTURE,
                kind=CapabilityKind.INTELLIGENCE,
                name="Architecture Review",
                version="1.0.0",
                description="Architecture analysis",
                input_schema={"observations": "list"},
                output_schema={"findings": "list", "recommendations": "list"},
                dependencies=[],
                advisory_only=True,
                owner=self.name,
            ),
        ]
        for cap in caps:
            orchestrator.registry.register(cap)
            orchestrator.register_handler(cap.capability_id, self._dispatch(cap.capability_id))

    def _dispatch(self, capability_id: str):
        def handler(request: CapabilityRequest) -> CapabilityResponse:
            lineage_id = str(uuid.uuid4())
            kind_map = {
                self.CAPABILITY_ANALYZE: request.inputs.get("specialist_kind", "DIAGNOSTICS"),
                self.CAPABILITY_DIAGNOSE: "DIAGNOSTICS",
                self.CAPABILITY_ARCHITECTURE: "ARCHITECTURE",
            }
            kind_str = kind_map.get(capability_id, "DIAGNOSTICS")
            try:
                kind = AISpecialistKind(kind_str)
            except ValueError:
                kind = AISpecialistKind.DIAGNOSTICS

            intel_req = IntelligenceRequest(
                request_id=request.request_id,
                specialist_kind=kind,
                context=request.context,
                observations=request.inputs.get("observations", []),
            )
            result = self._router.route(intel_req)
            sci_id = stable_hash({"capability": capability_id, "lineage": lineage_id})
            return CapabilityResponse(
                response_id=str(uuid.uuid4()),
                request_id=request.request_id,
                capability_id=capability_id,
                outputs={
                    "analysis": result.analysis,
                    "confidence": result.confidence,
                    "recommendations": result.recommendations,
                    "specialist_kind": str(result.specialist_kind),
                },
                evidence=result.evidence,
                confidence=result.confidence,
                advisory_only=True,
                lineage_id=lineage_id,
                scientific_id=sci_id,
            )
        return handler
