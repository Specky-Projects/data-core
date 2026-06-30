"""Research Engine — Contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ResearchKind(str, Enum):
    COMPARATIVE = "COMPARATIVE"
    ARCHITECTURE = "ARCHITECTURE"
    TECHNOLOGY = "TECHNOLOGY"
    OPPORTUNITY = "OPPORTUNITY"
    COMPETITIVE = "COMPETITIVE"
    SCIENTIFIC = "SCIENTIFIC"
    TREND = "TREND"


@dataclass
class ResearchResult:
    result_id: str
    kind: ResearchKind
    findings: list[dict]
    summary: str
    confidence: float
    sources: list[str]
    cached: bool = False
    advisory_only: bool = True
    produced_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        assert self.advisory_only is True
        assert isinstance(self.findings, list)
        assert 0.0 <= self.confidence <= 1.0
