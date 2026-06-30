"""Technical Debt capability."""
from __future__ import annotations

from typing import Any


class TechnicalDebtCapability:
    name = "technical_debt"

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "debt_items": [
                {"id": "TD-001", "description": "Missing integration tests for new engines", "effort": "MEDIUM"},
                {"id": "TD-002", "description": "Observation adapters need real connections", "effort": "HIGH"},
            ],
            "total_items": 2,
            "advisory_only": True,
        }
