"""ADR Generator capability."""
from __future__ import annotations

from typing import Any


class ADRGeneratorCapability:
    name = "adr_generator"

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        title = inputs.get("title", "Untitled Decision")
        context = inputs.get("context", "No context provided")
        decision = inputs.get("decision", "To be determined")
        return {
            "adr": {
                "title": title,
                "status": "PROPOSED",
                "context": context,
                "decision": decision,
                "consequences": inputs.get("consequences", []),
            },
            "advisory_only": True,
        }
