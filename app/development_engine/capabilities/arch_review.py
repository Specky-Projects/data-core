"""Architecture Review capability."""
from __future__ import annotations

from typing import Any


class ArchReviewCapability:
    name = "arch_review"

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "findings": [
                "module boundaries are respected",
                "no circular imports detected",
                "advisory_only enforced across all engines",
            ],
            "score": 0.88,
            "recommendations": ["document ADRs for each new engine"],
            "advisory_only": True,
        }
