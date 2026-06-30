"""Optimization Engine — advisory optimization suggestions."""
from __future__ import annotations

import uuid

from app.capability_orchestrator.contracts import (
    CapabilityKind,
    CapabilityRegistration,
    CapabilityRequest,
    CapabilityResponse,
)
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.optimization_engine.contracts import OptimizationKind
from app.optimization_engine.optimizers.ai_cost import AICostOptimizer
from app.optimization_engine.optimizers.architecture import ArchitectureOptimizer
from app.optimization_engine.optimizers.cache import CacheOptimizer
from app.optimization_engine.optimizers.cost import CostOptimizer
from app.optimization_engine.optimizers.database import DatabaseOptimizer
from app.optimization_engine.optimizers.infra import InfraOptimizer
from app.optimization_engine.optimizers.latency import LatencyOptimizer
from app.optimization_engine.priority_matrix import PriorityMatrix
from app.scientific_identity.contract import stable_hash


def _step_to_dict(step) -> dict:
    return {
        "step_id": step.step_id,
        "title": step.title,
        "description": step.description,
        "effort": step.effort,
        "impact": step.impact,
        "risk": step.risk,
        "estimated_gain": step.estimated_gain,
        "rollback_procedure": step.rollback_procedure,
        "validation_steps": step.validation_steps,
        "advisory_only": step.advisory_only,
    }


class OptimizationEngine:
    name = "optimization_engine"

    CAPABILITY_INFRA = "optimization.infra"
    CAPABILITY_DATABASE = "optimization.database"
    CAPABILITY_CACHE = "optimization.cache"
    CAPABILITY_AI_COST = "optimization.ai_cost"
    CAPABILITY_LATENCY = "optimization.latency"
    CAPABILITY_ARCHITECTURE = "optimization.architecture"
    CAPABILITY_COST = "optimization.cost"
    CAPABILITY_PRIORITIZE = "optimization.prioritize"

    def __init__(self) -> None:
        self._matrix = PriorityMatrix()
        self._optimizers = {
            self.CAPABILITY_INFRA: InfraOptimizer(),
            self.CAPABILITY_DATABASE: DatabaseOptimizer(),
            self.CAPABILITY_CACHE: CacheOptimizer(),
            self.CAPABILITY_AI_COST: AICostOptimizer(),
            self.CAPABILITY_LATENCY: LatencyOptimizer(),
            self.CAPABILITY_ARCHITECTURE: ArchitectureOptimizer(),
            self.CAPABILITY_COST: CostOptimizer(),
        }

    def register(self, orchestrator: CapabilityOrchestrator) -> None:
        all_ids = list(self._optimizers.keys()) + [self.CAPABILITY_PRIORITIZE]
        for cap_id in all_ids:
            name = cap_id.replace("optimization.", "").replace("_", " ").title()
            cap = CapabilityRegistration(
                capability_id=cap_id,
                kind=CapabilityKind.OPTIMIZATION,
                name=name,
                version="1.0.0",
                description=f"Advisory optimization: {name}",
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
            if capability_id == self.CAPABILITY_PRIORITIZE:
                all_steps = []
                for opt in self._optimizers.values():
                    all_steps.extend(opt.suggest(request.inputs))
                prioritized = self._matrix.prioritize(all_steps)
                outputs = {
                    "steps": [_step_to_dict(s) for s in prioritized],
                    "total": len(prioritized),
                    "advisory_only": True,
                }
            else:
                optimizer = self._optimizers.get(capability_id)
                steps = optimizer.suggest(request.inputs) if optimizer else []
                prioritized = self._matrix.prioritize(steps)
                outputs = {
                    "steps": [_step_to_dict(s) for s in prioritized],
                    "total": len(prioritized),
                    "advisory_only": True,
                }
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
