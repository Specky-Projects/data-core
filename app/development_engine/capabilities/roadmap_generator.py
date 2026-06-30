"""Roadmap Generator capability."""
from __future__ import annotations

from typing import Any


class RoadmapGeneratorCapability:
    name = "roadmap_generator"

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "roadmap": {
                "phases": inputs.get("phases", []),
                "horizon": inputs.get("horizon", "Q3-2026"),
                "priorities": inputs.get("priorities", []),
            },
            "advisory_only": True,
        }
