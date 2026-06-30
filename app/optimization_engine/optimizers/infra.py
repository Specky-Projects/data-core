"""Infra optimizer."""
from __future__ import annotations

import uuid
from typing import Any

from app.optimization_engine.contracts import OptimizationStep


class InfraOptimizer:
    name = "infra"

    def suggest(self, inputs: dict[str, Any]) -> list[OptimizationStep]:
        return [
            OptimizationStep(
                step_id=str(uuid.uuid4()),
                title="Reduce idle containers",
                description="Stop non-essential containers during off-peak hours",
                effort="LOW",
                impact="MEDIUM",
                risk="LOW",
                estimated_gain="10-20% cost reduction",
                rollback_procedure="docker compose up -d to restore all services",
                validation_steps=["check container health", "verify service endpoints"],
                advisory_only=True,
            )
        ]
