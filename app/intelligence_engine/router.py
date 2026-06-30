"""Intelligence Router — routes requests to appropriate specialists."""
from __future__ import annotations

from app.intelligence_engine.contracts import (
    AISpecialistKind,
    IntelligenceRequest,
    IntelligenceResult,
)
from app.intelligence_engine.specialists.mock import MockAISpecialist


class IntelligenceRouter:
    def __init__(self) -> None:
        self._default = MockAISpecialist()
        self._specialists: dict[str, object] = {
            kind: self._default for kind in AISpecialistKind
        }

    def route(self, request: IntelligenceRequest) -> IntelligenceResult:
        specialist = self._specialists.get(str(request.specialist_kind), self._default)
        return specialist.analyze(request)  # type: ignore[attr-defined]

    def register_specialist(self, kind: AISpecialistKind, specialist: object) -> None:
        self._specialists[str(kind)] = specialist
