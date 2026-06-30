"""Specification Generator capability."""
from __future__ import annotations

from typing import Any


class SpecificationCapability:
    name = "specification"

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        component = inputs.get("component", "unknown")
        return {
            "specification": {
                "component": component,
                "version": "1.0.0",
                "contracts": inputs.get("contracts", []),
                "dependencies": inputs.get("dependencies", []),
                "advisory_only": True,
            },
            "advisory_only": True,
        }
