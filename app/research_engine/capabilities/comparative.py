"""Comparative research capability."""
from __future__ import annotations

import uuid
from typing import Any

from app.research_engine.contracts import ResearchKind, ResearchResult


class ComparativeCapability:
    name = "comparative"

    def research(self, inputs: dict[str, Any]) -> ResearchResult:
        options = inputs.get("options", ["A", "B"])
        return ResearchResult(
            result_id=str(uuid.uuid4()),
            kind=ResearchKind.COMPARATIVE,
            findings=[{"option": o, "score": 0.7} for o in options],
            summary=f"Compared {len(options)} options",
            confidence=0.8,
            sources=["synthetic"],
            advisory_only=True,
        )
