"""Latency optimizer."""
from __future__ import annotations

import uuid
from typing import Any

from app.optimization_engine.contracts import OptimizationStep


class LatencyOptimizer:
    name = "latency"

    def suggest(self, inputs: dict[str, Any]) -> list[OptimizationStep]:
        return [
            OptimizationStep(
                step_id=str(uuid.uuid4()),
                title="Add connection pooling",
                description="Use PgBouncer to pool PostgreSQL connections",
                effort="MEDIUM",
                impact="HIGH",
                risk="MEDIUM",
                estimated_gain="20-30% latency reduction under load",
                rollback_procedure="point app directly to PostgreSQL, remove PgBouncer from compose",
                validation_steps=["p99 latency < 100ms", "connection count stable"],
                advisory_only=True,
            )
        ]
