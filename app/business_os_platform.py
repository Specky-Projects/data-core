"""BusinessOSPlatform — integrates all 7 engines via CapabilityOrchestrator.

This is the top-level integration point. Engines register capabilities;
BusinessOSPlatform routes requests through the orchestrator.
"""
from __future__ import annotations

import uuid

from app.capability_orchestrator.contracts import CapabilityKind, CapabilityResponse
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.capability_orchestrator.registry import CapabilityRegistry
from app.decision_engine.engine import DecisionEngine
from app.development_engine.engine import DevelopmentEngine
from app.intelligence_engine.engine import IntelligenceEngine
from app.knowledge_engine.engine import KnowledgeEngine
from app.observation_engine.engine import ObservationEngine
from app.optimization_engine.engine import OptimizationEngine
from app.research_engine.engine import ResearchEngine

BUSINESS_OS_PLATFORM_VERSION = "business-os-platform-v1"


class BusinessOSPlatform:
    def __init__(self) -> None:
        self.orchestrator = CapabilityOrchestrator(CapabilityRegistry())
        self._engines: dict[str, object] = {}
        self._started = False

    def startup(self) -> None:
        engines = [
            ObservationEngine(),
            IntelligenceEngine(),
            DevelopmentEngine(),
            ResearchEngine(),
            OptimizationEngine(),
            KnowledgeEngine(),
            DecisionEngine(),
        ]
        for engine in engines:
            engine.register(self.orchestrator)  # type: ignore[attr-defined]
            self._engines[engine.name] = engine  # type: ignore[attr-defined]
        self._started = True

    def execute(self, capability_id: str, inputs: dict) -> CapabilityResponse:
        assert self._started, "Call startup() before execute()"
        from app.capability_orchestrator.contracts import CapabilityRequest
        request = CapabilityRequest(
            request_id=str(uuid.uuid4()),
            capability_id=capability_id,
            inputs=inputs,
            context={"platform": "business-os", "version": BUSINESS_OS_PLATFORM_VERSION},
        )
        return self.orchestrator.execute(request)

    def status(self) -> dict:
        return {
            "started": self._started,
            "engines": list(self._engines.keys()),
            "capabilities_count": len(self.orchestrator.registered_ids()),
            "capability_ids": self.orchestrator.registered_ids(),
            "version": BUSINESS_OS_PLATFORM_VERSION,
        }

    def capabilities_by_kind(self, kind: str) -> list[str]:
        try:
            ck = CapabilityKind(kind)
        except ValueError:
            return []
        return [c.capability_id for c in self.orchestrator.discover(ck)]
