"""Cost optimizer."""
from __future__ import annotations

import uuid
from typing import Any

from app.optimization_engine.contracts import OptimizationStep


class CostOptimizer:
    name = "cost"

    def suggest(self, inputs: dict[str, Any]) -> list[OptimizationStep]:
        return [
            OptimizationStep(
                step_id=str(uuid.uuid4()),
                title="Downsize VPS to match actual load",
                description="Current VPS is over-provisioned; reduce to next tier",
                effort="LOW",
                impact="MEDIUM",
                risk="LOW",
                estimated_gain="25-35% monthly hosting cost reduction",
                rollback_procedure="scale back up via VPS provider dashboard in < 10 minutes",
                validation_steps=["CPU < 70% at peak", "memory < 80% at peak"],
                advisory_only=True,
            )
        ]
