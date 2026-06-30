"""Test Planner capability."""
from __future__ import annotations

from typing import Any


class TestPlannerCapability:
    name = "test_planner"

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        component = inputs.get("component", "unknown")
        return {
            "test_plan": {
                "component": component,
                "unit_tests": ["test_contracts", "test_engine_basic"],
                "integration_tests": ["test_orchestrator_registration"],
                "coverage_target": 0.80,
            },
            "advisory_only": True,
        }
