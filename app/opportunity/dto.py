"""Business OS 1.5 — Opportunity Intelligence Platform — Canonical Opportunity Model.

Stage 1: Canonical Opportunity DTO hierarchy.

Scientific constraints:
  - Deterministic: all IDs derived from content, not wall-clock
  - Replay-safe: EvaluationContext is the single time reference
  - Evidence-anchored: every score exposes its evidence basis
  - Full provenance: every Opportunity carries lineage
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.adaptive_intelligence.dto import EvaluationContext, ScientificVersionMetadata
from app.knowledge.dto import (
    KNOWLEDGE_VERSION,
    KnowledgeCorrelation,
    KnowledgeEntity,
    KnowledgeEvidence,
    KnowledgeRelationship,
    KnowledgeSource,
    KnowledgeVersionMetadata,
    _EPOCH,
    _k_stable_hash,
)

# ── Version constants ──────────────────────────────────────────────────────────

OPPORTUNITY_VERSION = "business-os-1.5-opportunity"
DISCOVERY_VERSION = "opportunity-discovery-v1-1.5"
SCORING_VERSION = "opportunity-scoring-v1-1.5"
RANKING_VERSION = "opportunity-ranking-v1-1.5"
LIFECYCLE_VERSION = "opportunity-lifecycle-v1-1.5"
PORTFOLIO_VERSION = "opportunity-portfolio-v1-1.5"
HEALTH_VERSION = "opportunity-health-v1-1.5"
EXPLAINABILITY_VERSION = "opportunity-explainability-v1-1.5"
EVOLUTION_VERSION = "opportunity-evolution-v1-1.5"

# ── Enumerations ───────────────────────────────────────────────────────────────


class OpportunityType(str, Enum):
    TECHNOLOGY = "technology"
    MARKET = "market"
    RESEARCH = "research"
    PRODUCT = "product"
    TALENT = "talent"
    PARTNERSHIP = "partnership"
    OPEN_SOURCE = "open_source"
    INFRASTRUCTURE = "infrastructure"
    UNKNOWN = "unknown"


class LifecycleStage(str, Enum):
    NEW = "new"
    EARLY = "early"
    GROWING = "growing"
    MATURE = "mature"
    DECLINING = "declining"
    ARCHIVED = "archived"


class RankingStrategy(str, Enum):
    BY_CONFIDENCE = "by_confidence"
    BY_NOVELTY = "by_novelty"
    BY_IMPACT = "by_impact"
    BY_COMPOSITE = "by_composite"
    BY_URGENCY = "by_urgency"
    BY_FRESHNESS = "by_freshness"


class EvolutionDirection(str, Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    UNKNOWN = "unknown"


# ── Version Metadata ───────────────────────────────────────────────────────────


class OpportunityVersionMetadata(BaseModel):
    opportunity_version: str = OPPORTUNITY_VERSION
    discovery_version: str = DISCOVERY_VERSION
    scoring_version: str = SCORING_VERSION
    ranking_version: str = RANKING_VERSION
    lifecycle_version: str = LIFECYCLE_VERSION
    portfolio_version: str = PORTFOLIO_VERSION
    health_version: str = HEALTH_VERSION
    explainability_version: str = EXPLAINABILITY_VERSION
    evolution_version: str = EVOLUTION_VERSION
    knowledge_version: str = KNOWLEDGE_VERSION


# ── Opportunity Score (Stage 3) ────────────────────────────────────────────────


class OpportunityScore(BaseModel):
    """10-dimension evidence-derived opportunity score."""

    novelty: float = Field(ge=0.0, le=1.0, default=0.0)
    evidence_strength: float = Field(ge=0.0, le=1.0, default=0.0)
    source_diversity: float = Field(ge=0.0, le=1.0, default=0.0)
    growth_velocity: float = Field(ge=0.0, le=1.0, default=0.0)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    risk: float = Field(ge=0.0, le=1.0, default=0.0)
    market_impact: float = Field(ge=0.0, le=1.0, default=0.0)
    strategic_relevance: float = Field(ge=0.0, le=1.0, default=0.0)
    consistency: float = Field(ge=0.0, le=1.0, default=0.0)
    freshness: float = Field(ge=0.0, le=1.0, default=0.0)
    composite_score: float = Field(ge=0.0, le=1.0, default=0.0)
    evidence_ids: list[str] = Field(default_factory=list)
    versions: OpportunityVersionMetadata = Field(default_factory=OpportunityVersionMetadata)

    def model_post_init(self, __context: Any) -> None:
        if self.composite_score == 0.0:
            dims = [
                self.novelty, self.evidence_strength, self.source_diversity,
                self.growth_velocity, self.confidence, self.market_impact,
                self.strategic_relevance, self.consistency, self.freshness,
            ]
            self.composite_score = round(sum(dims) / len(dims), 4)


# ── Opportunity Provenance ─────────────────────────────────────────────────────


class OpportunityProvenance(BaseModel):
    """Full lineage: which knowledge items generated this opportunity."""

    knowledge_item_ids: list[str] = Field(default_factory=list)
    correlation_ids: list[str] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    discovery_method: str = ""
    discovered_at: datetime = _EPOCH
    versions: OpportunityVersionMetadata = Field(default_factory=OpportunityVersionMetadata)
    provenance_hash: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.provenance_hash:
            self.provenance_hash = _k_stable_hash({
                "items": sorted(self.knowledge_item_ids)[:25],
                "method": self.discovery_method,
                "versions": self.versions.opportunity_version,
            })


# ── Opportunity Explanation (Stage 9) ─────────────────────────────────────────


class OpportunityExplanation(BaseModel):
    """Why this opportunity exists and why it changed."""

    why_exists: str = ""
    evidence_basis: list[str] = Field(default_factory=list)
    entity_roles: dict[str, str] = Field(default_factory=dict)
    source_contributions: dict[str, float] = Field(default_factory=dict)
    confidence_rationale: str = ""
    ranking_rationale: str = ""
    lifecycle_rationale: str = ""
    versions: OpportunityVersionMetadata = Field(default_factory=OpportunityVersionMetadata)


# ── Opportunity Evolution Snapshot (Stage 6) ──────────────────────────────────


class OpportunityEvolutionSnapshot(BaseModel):
    """Point-in-time snapshot of an opportunity's key metrics."""

    snapshot_id: str
    opportunity_id: str
    evaluation_timestamp: datetime = _EPOCH
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    priority: float = Field(ge=0.0, le=1.0, default=0.0)
    composite_score: float = Field(ge=0.0, le=1.0, default=0.0)
    lifecycle_stage: LifecycleStage = LifecycleStage.NEW
    evidence_count: int = 0
    source_count: int = 0
    entity_count: int = 0
    versions: OpportunityVersionMetadata = Field(default_factory=OpportunityVersionMetadata)


def build_snapshot_id(opportunity_id: str, evaluation_timestamp: datetime) -> str:
    return _k_stable_hash({"opp": opportunity_id, "ts": evaluation_timestamp.isoformat()})


# ── Core Opportunity DTO (Stage 1) ─────────────────────────────────────────────


class Opportunity(BaseModel):
    """Canonical Opportunity — the primary output of the Opportunity layer."""

    opportunity_id: str
    title: str
    summary: str
    description: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    priority: float = Field(ge=0.0, le=1.0, default=0.0)
    novelty: float = Field(ge=0.0, le=1.0, default=0.0)
    maturity: float = Field(ge=0.0, le=1.0, default=0.0)
    urgency: float = Field(ge=0.0, le=1.0, default=0.0)
    impact: float = Field(ge=0.0, le=1.0, default=0.0)
    opportunity_type: OpportunityType = OpportunityType.UNKNOWN
    market: str = ""
    domain: str = ""
    evidence: list[KnowledgeEvidence] = Field(default_factory=list)
    entities: list[KnowledgeEntity] = Field(default_factory=list)
    relationships: list[KnowledgeRelationship] = Field(default_factory=list)
    sources: list[KnowledgeSource] = Field(default_factory=list)
    correlations: list[KnowledgeCorrelation] = Field(default_factory=list)
    provenance: OpportunityProvenance
    score: OpportunityScore = Field(default_factory=OpportunityScore)
    explanation: OpportunityExplanation = Field(default_factory=OpportunityExplanation)
    lifecycle_stage: LifecycleStage = LifecycleStage.NEW
    evolution_history: list[OpportunityEvolutionSnapshot] = Field(default_factory=list)
    versions: OpportunityVersionMetadata = Field(default_factory=OpportunityVersionMetadata)
    created_at: datetime = _EPOCH
    updated_at: datetime = _EPOCH
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_opportunity_id(title: str, domain: str, opportunity_type: OpportunityType) -> str:
    return _k_stable_hash({
        "title": title.lower().strip(),
        "domain": domain.lower().strip(),
        "type": opportunity_type.value,
    })


# ── Opportunity Health (Stage 8) ───────────────────────────────────────────────


class OpportunityHealth(BaseModel):
    """10-dimension health model for the Opportunity layer."""

    evidence_quality: float = Field(ge=0.0, le=1.0, default=0.0)
    freshness: float = Field(ge=0.0, le=1.0, default=0.0)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    consistency: float = Field(ge=0.0, le=1.0, default=0.0)
    coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    source_diversity: float = Field(ge=0.0, le=1.0, default=0.0)
    market_activity: float = Field(ge=0.0, le=1.0, default=0.0)
    historical_stability: float = Field(ge=0.0, le=1.0, default=0.0)
    novelty: float = Field(ge=0.0, le=1.0, default=0.0)
    explainability: float = Field(ge=0.0, le=1.0, default=0.0)
    health_score: float = Field(ge=0.0, le=1.0, default=0.0)
    opportunity_count: int = 0
    versions: OpportunityVersionMetadata = Field(default_factory=OpportunityVersionMetadata)


# ── Opportunity Portfolio (Stage 7) ───────────────────────────────────────────


class PortfolioNode(BaseModel):
    """Node in the hierarchical opportunity portfolio."""

    node_id: str
    label: str
    domain: str
    market: str = ""
    opportunity_count: int = 0
    opportunity_ids: list[str] = Field(default_factory=list)
    children: list["PortfolioNode"] = Field(default_factory=list)
    composite_score: float = Field(ge=0.0, le=1.0, default=0.0)
    versions: OpportunityVersionMetadata = Field(default_factory=OpportunityVersionMetadata)


# ── Opportunity Report (top-level output) ─────────────────────────────────────


class OpportunityReport(BaseModel):
    """Top-level output of the Opportunity pipeline."""

    report_id: str
    opportunities: list[Opportunity] = Field(default_factory=list)
    ranked_opportunities: list[Opportunity] = Field(default_factory=list)
    portfolio: list[PortfolioNode] = Field(default_factory=list)
    health: OpportunityHealth
    versions: OpportunityVersionMetadata = Field(default_factory=OpportunityVersionMetadata)
    evaluation_context: EvaluationContext | None = None
    generated_at: datetime = _EPOCH
    ranking_strategy: RankingStrategy = RankingStrategy.BY_COMPOSITE
    knowledge_item_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
