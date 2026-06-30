"""Decision Engine — Contracts.

DecisionEngine is ALWAYS advisory_only=True.
It NEVER executes actions — only provides structured recommendations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class DecisionKind(StrEnum):
    ACT = "ACT"
    DONT_ACT = "DONT_ACT"
    DEFER = "DEFER"
    INVESTIGATE = "INVESTIGATE"


@dataclass(frozen=True)
class DecisionRequest:
    request_id: str
    context: dict[str, Any]
    evidence: list[str]
    confidence_threshold: float = 0.7
    requested_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DecisionResult:
    decision_id: str
    scientific_id: str
    lineage_id: str
    decision: DecisionKind
    rationale: str
    confidence: float
    evidence: list[str]
    advisory_only: bool = True
    decided_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        assert self.advisory_only is True, "DecisionEngine is always advisory_only — never executes"
        assert 0.0 <= self.confidence <= 1.0


class PolicyEvaluator:
    """Evaluates context against simple heuristic policies."""

    def evaluate(self, context: dict, evidence: list[str], threshold: float) -> DecisionKind:
        confidence = context.get("confidence", 0.5)
        health = context.get("health", "UNKNOWN")

        if health == "CRITICAL":
            return DecisionKind.INVESTIGATE
        if confidence >= threshold:
            return DecisionKind.ACT
        if confidence >= threshold * 0.7:
            return DecisionKind.DEFER
        return DecisionKind.DONT_ACT
