"""Intelligence Engine — Contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AISpecialistKind(str, Enum):
    DIAGNOSTICS = "DIAGNOSTICS"
    ARCHITECTURE = "ARCHITECTURE"
    PERFORMANCE = "PERFORMANCE"
    SECURITY = "SECURITY"
    COST = "COST"
    STRATEGY = "STRATEGY"
    ANOMALY = "ANOMALY"


@dataclass(frozen=True)
class IntelligenceRequest:
    request_id: str
    specialist_kind: AISpecialistKind
    context: dict[str, Any]
    observations: list[dict]
    requested_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class IntelligenceResult:
    result_id: str
    request_id: str
    specialist_kind: AISpecialistKind
    analysis: dict[str, Any]   # ALWAYS structured dict — never bare string
    confidence: float
    evidence: list[str]
    recommendations: list[str]
    advisory_only: bool = True
    produced_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        assert self.advisory_only is True, "IntelligenceResult must always be advisory_only"
        assert isinstance(self.analysis, dict), "analysis must be a dict — never a bare string"
        assert 0.0 <= self.confidence <= 1.0, "confidence must be between 0 and 1"
