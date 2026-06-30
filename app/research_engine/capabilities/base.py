"""Base protocol for research capabilities."""
from __future__ import annotations

from typing import Any, Protocol

from app.research_engine.contracts import ResearchResult


class ResearchCapability(Protocol):
    name: str

    def research(self, inputs: dict[str, Any]) -> ResearchResult: ...
