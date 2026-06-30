"""Knowledge Engine — Contracts.

Pipeline: ObservationRecord → TruthCandidate → [Insight] → [Recommendation]
          → [ExecutionPlan] → KnowledgeCandidate → (confidence >= 0.6) → Knowledge → ScientificMemory
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class KnowledgeScope(StrEnum):
    LOCAL = "LOCAL"
    PROJECT = "PROJECT"
    ECOSYSTEM = "ECOSYSTEM"


class KnowledgeStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    DEMOTED = "DEMOTED"
    SUPERSEDED = "SUPERSEDED"


@dataclass
class TruthCandidate:
    candidate_id: str
    observation_id: str
    proposition: str
    domain: str
    project: str
    confidence: float
    evidence: list[str]
    advisory_only: bool = True

    def __post_init__(self) -> None:
        assert self.advisory_only is True
        assert 0.0 <= self.confidence <= 1.0


@dataclass
class Insight:
    insight_id: str
    candidate_id: str
    title: str
    description: str
    confidence: float
    advisory_only: bool = True


@dataclass
class Recommendation:
    recommendation_id: str
    insight_id: str
    action: str
    rationale: str
    confidence: float
    advisory_only: bool = True


@dataclass
class ExecutionPlan:
    plan_id: str
    recommendation_id: str
    steps: list[str]
    estimated_effort: str
    advisory_only: bool = True

    def __post_init__(self) -> None:
        assert self.advisory_only is True


@dataclass
class KnowledgeCandidate:
    candidate_id: str
    truth_candidate_id: str
    title: str
    proposition: str
    domain: str
    project: str
    scope: KnowledgeScope
    evidence: list[str]
    confidence: float
    advisory_only: bool = True

    def __post_init__(self) -> None:
        assert self.advisory_only is True
        assert 0.0 <= self.confidence <= 1.0


@dataclass
class Knowledge:
    knowledge_id: str
    scientific_id: str
    lineage_id: str
    title: str
    proposition: str
    domain: str
    project: str
    scope: KnowledgeScope
    evidence: list[str]
    confidence: float
    version_number: int = 1
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        assert self.evidence, "Knowledge requires at least one evidence reference"
        assert 0.0 <= self.confidence <= 1.0
