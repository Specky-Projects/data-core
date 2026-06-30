"""Base protocol for AI specialists."""
from __future__ import annotations

from typing import Protocol

from app.intelligence_engine.contracts import IntelligenceRequest, IntelligenceResult


class AISpecialist(Protocol):
    kind: str

    def analyze(self, request: IntelligenceRequest) -> IntelligenceResult: ...
