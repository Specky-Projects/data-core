"""Business OS 1.4 — Universal Knowledge Platform — Canonical Knowledge Model.

All DTOs are source-independent. Source-specific payloads stay inside adapters.
Scientific constraints preserved: deterministic replay, zero production wall-clock,
evidence-derived calculations, full provenance.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.adaptive_intelligence.dto import EvaluationContext, ScientificVersionMetadata

# ── Version constants ──────────────────────────────────────────────────────────

KNOWLEDGE_VERSION = "business-os-1.4-knowledge"
CONNECTOR_VERSION = "knowledge-connectors-v1-1.4"
ENTITY_RESOLUTION_VERSION = "entity-resolution-v1-1.4"
FUSION_VERSION = "knowledge-fusion-v1-1.4"
CORRELATION_VERSION = "cross-source-correlation-v1-1.4"
GRAPH_VERSION = "knowledge-graph-v1-1.4"
PROVENANCE_VERSION = "knowledge-provenance-v1-1.4"

_EPOCH = datetime.fromisoformat("1970-01-01T00:00:00+00:00")

# ── Enumerations ───────────────────────────────────────────────────────────────


class SourceType(str, Enum):
    GITHUB = "github"
    HACKER_NEWS = "hacker_news"
    RSS = "rss"
    BLOG = "blog"
    MEDIUM = "medium"
    DEVTO = "devto"
    STACKOVERFLOW = "stackoverflow"
    ARXIV = "arxiv"
    PRODUCT_HUNT = "product_hunt"
    DOCS = "docs"
    GENERIC_API = "generic_api"
    YOUTUBE = "youtube"
    UNKNOWN = "unknown"


class EntityType(str, Enum):
    TECHNOLOGY = "technology"
    PERSON = "person"
    ORGANIZATION = "organization"
    TOPIC = "topic"
    PRODUCT = "product"
    REPOSITORY = "repository"
    UNKNOWN = "unknown"


class RelationshipType(str, Enum):
    MENTIONS = "mentions"
    DISCUSSES = "discusses"
    COMPARES = "compares"
    IMPLEMENTS = "implements"
    DEPENDS_ON = "depends_on"
    RELATED_TO = "related_to"
    CO_OCCURS_WITH = "co_occurs_with"


class CorrelationSignal(str, Enum):
    INCREASING_MENTIONS = "increasing_mentions"
    GROWING_COMMUNITY = "growing_community"
    EMERGING_TECHNOLOGY = "emerging_technology"
    DECLINING_INTEREST = "declining_interest"
    CROSS_SOURCE_CONVERGENCE = "cross_source_convergence"
    SUSTAINED_ATTENTION = "sustained_attention"


class FusionStrategy(str, Enum):
    ENTITY_OVERLAP = "entity_overlap"
    TOPIC_OVERLAP = "topic_overlap"
    URL_CANONICAL = "url_canonical"
    TITLE_SIMILARITY = "title_similarity"


# ── Utilities ──────────────────────────────────────────────────────────────────


def _k_stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def _k_stable_hash(obj: Any) -> str:
    return hashlib.sha256(_k_stable_json(obj).encode()).hexdigest()[:32]


def _normalize_entity_name(name: str) -> str:
    import re
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", " ", name)
    tokens = sorted(name.split())
    return " ".join(t for t in tokens if t)


# ── Knowledge Version Metadata ─────────────────────────────────────────────────


class KnowledgeVersionMetadata(BaseModel):
    knowledge_version: str = KNOWLEDGE_VERSION
    connector_version: str = CONNECTOR_VERSION
    entity_resolution_version: str = ENTITY_RESOLUTION_VERSION
    fusion_version: str = FUSION_VERSION
    correlation_version: str = CORRELATION_VERSION
    graph_version: str = GRAPH_VERSION
    provenance_version: str = PROVENANCE_VERSION


# ── Source ─────────────────────────────────────────────────────────────────────


class KnowledgeSource(BaseModel):
    source_id: str
    source_type: SourceType
    url: str
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Evidence ───────────────────────────────────────────────────────────────────


class KnowledgeEvidence(BaseModel):
    evidence_id: str
    content: str
    source_id: str
    item_url: str = ""
    weight: float = Field(ge=0.0, le=1.0, default=1.0)
    timestamp: datetime = _EPOCH
    evidence_type: str = "text"


def build_evidence_id(source_id: str, content: str, timestamp: datetime) -> str:
    return _k_stable_hash({"source_id": source_id, "content": content[:128], "ts": timestamp.isoformat()})


# ── Entity ─────────────────────────────────────────────────────────────────────


class EntityCandidate(BaseModel):
    raw_name: str
    entity_type: EntityType = EntityType.UNKNOWN
    context: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class EntityProvenance(BaseModel):
    first_seen_source: str
    evidence_ids: list[str] = Field(default_factory=list)
    mention_count: int = 0
    sources_count: int = 1
    versions: KnowledgeVersionMetadata = Field(default_factory=KnowledgeVersionMetadata)


class KnowledgeEntity(BaseModel):
    entity_id: str
    canonical_name: str
    normalized_name: str
    aliases: list[str] = Field(default_factory=list)
    entity_type: EntityType = EntityType.UNKNOWN
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    provenance: EntityProvenance
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_entity_id(name: str, entity_type: EntityType) -> str:
    normalized = _normalize_entity_name(name)
    return _k_stable_hash({"name": normalized, "type": entity_type.value})


# ── Provenance ─────────────────────────────────────────────────────────────────


class KnowledgeProvenance(BaseModel):
    original_source: str
    normalized_by: str
    entity_lineage: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    discovered_at: datetime = _EPOCH
    published_at: datetime | None = None
    normalization_history: list[str] = Field(default_factory=list)
    versions: KnowledgeVersionMetadata = Field(default_factory=KnowledgeVersionMetadata)
    provenance_hash: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.provenance_hash:
            self.provenance_hash = _k_stable_hash({
                "source": self.original_source,
                "evidence": sorted(self.evidence_ids)[:25],
                "versions": self.versions.model_dump(mode="json"),
            })


def build_knowledge_provenance(
    *,
    source_id: str,
    connector_name: str,
    evaluation_context: EvaluationContext,
    evidence_ids: list[str],
    published_at: datetime | None = None,
    entity_lineage: list[str] | None = None,
) -> KnowledgeProvenance:
    return KnowledgeProvenance(
        original_source=source_id,
        normalized_by=connector_name,
        entity_lineage=entity_lineage or [],
        evidence_ids=sorted(evidence_ids)[:25],
        discovered_at=evaluation_context.evaluation_timestamp,
        published_at=published_at,
        normalization_history=[connector_name],
        versions=KnowledgeVersionMetadata(),
    )


# ── Freshness ──────────────────────────────────────────────────────────────────


class KnowledgeFreshness(BaseModel):
    source_freshness: float = Field(ge=0.0, le=1.0)
    entity_freshness: float = Field(ge=0.0, le=1.0)
    evidence_freshness: float = Field(ge=0.0, le=1.0)
    knowledge_freshness: float = Field(ge=0.0, le=1.0)
    age_days: float = 0.0
    evaluated_at: datetime = _EPOCH


def compute_knowledge_freshness(
    *,
    published_at: datetime | None,
    evaluation_context: EvaluationContext,
    half_life_days: float = 30.0,
    min_freshness: float = 0.05,
) -> KnowledgeFreshness:
    ref_ts = evaluation_context.evaluation_timestamp
    if published_at is None:
        base = min_freshness
        age_days = 0.0
    else:
        age_days = max(0.0, (ref_ts.timestamp() - published_at.timestamp()) / 86_400.0)
        import math
        base = max(min_freshness, math.exp(-age_days / half_life_days))

    return KnowledgeFreshness(
        source_freshness=base,
        entity_freshness=base,
        evidence_freshness=base,
        knowledge_freshness=base,
        age_days=age_days,
        evaluated_at=ref_ts,
    )


# ── Canonical Knowledge Item ───────────────────────────────────────────────────


class KnowledgeItem(BaseModel):
    item_id: str
    title: str
    summary: str
    url: str
    content: str | None = None
    author: str | None = None
    source: KnowledgeSource
    entities: list[KnowledgeEntity] = Field(default_factory=list)
    evidence: list[KnowledgeEvidence] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    provenance: KnowledgeProvenance
    freshness: KnowledgeFreshness
    versions: KnowledgeVersionMetadata = Field(default_factory=KnowledgeVersionMetadata)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    engagement_score: float = Field(ge=0.0, default=0.0)
    published_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_item_id(url: str, source_id: str) -> str:
    return _k_stable_hash({"url": url, "source_id": source_id})


# ── Fused Knowledge Item ───────────────────────────────────────────────────────


class FusedKnowledgeItem(BaseModel):
    fusion_id: str
    primary_item: KnowledgeItem
    contributing_items: list[KnowledgeItem] = Field(default_factory=list)
    merged_entities: list[KnowledgeEntity] = Field(default_factory=list)
    merged_evidence: list[KnowledgeEvidence] = Field(default_factory=list)
    merged_topics: list[str] = Field(default_factory=list)
    source_count: int = 1
    fusion_strategy: FusionStrategy = FusionStrategy.ENTITY_OVERLAP
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    versions: KnowledgeVersionMetadata = Field(default_factory=KnowledgeVersionMetadata)
    fusion_hash: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.fusion_hash:
            ids = sorted([self.primary_item.item_id] + [i.item_id for i in self.contributing_items])
            self.fusion_hash = _k_stable_hash({"ids": ids, "strategy": self.fusion_strategy.value})


# ── Knowledge Relationship (Logical Graph) ─────────────────────────────────────


class KnowledgeRelationship(BaseModel):
    relationship_id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: RelationshipType
    strength: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    co_occurrence_count: int = 0
    source_ids: list[str] = Field(default_factory=list)
    versions: KnowledgeVersionMetadata = Field(default_factory=KnowledgeVersionMetadata)


def build_relationship_id(source_entity_id: str, target_entity_id: str, rel_type: RelationshipType) -> str:
    ids = sorted([source_entity_id, target_entity_id])
    return _k_stable_hash({"entities": ids, "type": rel_type.value})


# ── Correlation ────────────────────────────────────────────────────────────────


class KnowledgeCorrelation(BaseModel):
    correlation_id: str
    entities: list[str]
    signal: CorrelationSignal
    strength: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    explanation: str = ""
    window_days: int = 30
    versions: KnowledgeVersionMetadata = Field(default_factory=KnowledgeVersionMetadata)


def build_correlation_id(entities: list[str], signal: CorrelationSignal, window_days: int) -> str:
    return _k_stable_hash({"entities": sorted(entities), "signal": signal.value, "window": window_days})


# ── Knowledge Health ───────────────────────────────────────────────────────────


class KnowledgeHealth(BaseModel):
    coverage: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    source_diversity: float = Field(ge=0.0, le=1.0)
    evidence_quality: float = Field(ge=0.0, le=1.0)
    entity_resolution_quality: float = Field(ge=0.0, le=1.0)
    correlation_strength: float = Field(ge=0.0, le=1.0)
    knowledge_density: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(ge=0.0, le=1.0)
    explainability: float = Field(ge=0.0, le=1.0)
    version_consistency: float = Field(ge=0.0, le=1.0)
    health_score: float = Field(ge=0.0, le=1.0)
    item_count: int = 0
    entity_count: int = 0
    source_count: int = 0
    versions: KnowledgeVersionMetadata = Field(default_factory=KnowledgeVersionMetadata)


def compute_knowledge_health(
    *,
    items: list[KnowledgeItem],
    fused: list[FusedKnowledgeItem],
    correlations: list[KnowledgeCorrelation],
    relationships: list[KnowledgeRelationship],
    evaluation_context: EvaluationContext,
) -> KnowledgeHealth:
    if not items:
        return KnowledgeHealth(
            coverage=0.0, freshness=0.0, source_diversity=0.0, evidence_quality=0.0,
            entity_resolution_quality=0.0, correlation_strength=0.0, knowledge_density=0.0,
            completeness=0.0, explainability=0.0, version_consistency=0.0, health_score=0.0,
        )

    sources = {i.source.source_id for i in items}
    source_types = {i.source.source_type for i in items}
    n = len(items)

    freshness_avg = sum(i.freshness.knowledge_freshness for i in items) / n
    evidence_per_item = sum(len(i.evidence) for i in items) / n
    entities_per_item = sum(len(i.entities) for i in items) / n

    coverage = min(1.0, n / max(10, n))
    source_diversity = min(1.0, len(source_types) / 4.0)
    evidence_quality = min(1.0, evidence_per_item / 3.0)
    entity_resolution_quality = min(1.0, len(fused) / max(1, n) * 2.0) if fused else 0.5
    correlation_strength = (sum(c.strength for c in correlations) / len(correlations)) if correlations else 0.0
    knowledge_density = min(1.0, entities_per_item / 5.0)
    completeness = min(1.0, (len(sources) / 2.0) * (evidence_quality))
    explainability = min(1.0, (len(relationships) / max(1, len(items))) * 2.0) if relationships else 0.5

    versions_ok = all(
        i.versions.knowledge_version == KNOWLEDGE_VERSION for i in items
    )
    version_consistency = 1.0 if versions_ok else 0.0

    dims = [
        coverage, freshness_avg, source_diversity, evidence_quality,
        entity_resolution_quality, correlation_strength, knowledge_density,
        completeness, explainability, version_consistency,
    ]
    health_score = sum(dims) / len(dims)

    return KnowledgeHealth(
        coverage=round(coverage, 4),
        freshness=round(freshness_avg, 4),
        source_diversity=round(source_diversity, 4),
        evidence_quality=round(evidence_quality, 4),
        entity_resolution_quality=round(entity_resolution_quality, 4),
        correlation_strength=round(correlation_strength, 4),
        knowledge_density=round(knowledge_density, 4),
        completeness=round(completeness, 4),
        explainability=round(explainability, 4),
        version_consistency=round(version_consistency, 4),
        health_score=round(health_score, 4),
        item_count=n,
        entity_count=len({e.entity_id for i in items for e in i.entities}),
        source_count=len(sources),
    )


# ── Knowledge Report (top-level pipeline output) ───────────────────────────────


class KnowledgeReport(BaseModel):
    report_id: str
    items: list[KnowledgeItem] = Field(default_factory=list)
    fused_items: list[FusedKnowledgeItem] = Field(default_factory=list)
    correlations: list[KnowledgeCorrelation] = Field(default_factory=list)
    relationships: list[KnowledgeRelationship] = Field(default_factory=list)
    health: KnowledgeHealth
    versions: KnowledgeVersionMetadata = Field(default_factory=KnowledgeVersionMetadata)
    evaluation_context: EvaluationContext | None = None
    generated_at: datetime = _EPOCH


# ── Shadow Contracts (future execution interfaces) ─────────────────────────────


class Goal(BaseModel):
    """Future interface — Business OS 1.5+. No runtime behavior."""
    goal_id: str
    description: str
    priority: float = Field(ge=0.0, le=1.0, default=0.5)
    knowledge_basis: list[str] = Field(default_factory=list)
    status: Literal["pending", "active", "achieved", "abandoned"] = "pending"
    versions: KnowledgeVersionMetadata = Field(default_factory=KnowledgeVersionMetadata)


class Decision(BaseModel):
    """Future interface — Business OS 1.5+. No runtime behavior."""
    decision_id: str
    description: str
    goal_id: str | None = None
    rationale: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["draft", "approved", "rejected", "superseded"] = "draft"
    versions: KnowledgeVersionMetadata = Field(default_factory=KnowledgeVersionMetadata)


class ExecutionTask(BaseModel):
    """Future interface — Business OS 1.5+. No runtime behavior."""
    task_id: str
    description: str
    task_type: str = "unspecified"
    priority: float = Field(ge=0.0, le=1.0, default=0.5)
    dependencies: list[str] = Field(default_factory=list)
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = "pending"
    versions: KnowledgeVersionMetadata = Field(default_factory=KnowledgeVersionMetadata)


class ExecutionPlan(BaseModel):
    """Future interface — Business OS 1.5+. No runtime behavior."""
    plan_id: str
    goal_id: str | None = None
    decision_id: str | None = None
    tasks: list[ExecutionTask] = Field(default_factory=list)
    status: Literal["draft", "active", "completed", "aborted"] = "draft"
    versions: KnowledgeVersionMetadata = Field(default_factory=KnowledgeVersionMetadata)


class ExecutionResult(BaseModel):
    """Future interface — Business OS 1.5+. No runtime behavior."""
    result_id: str
    plan_id: str
    task_id: str
    outcome: Literal["success", "failure", "partial", "unknown"] = "unknown"
    evidence: list[str] = Field(default_factory=list)
    versions: KnowledgeVersionMetadata = Field(default_factory=KnowledgeVersionMetadata)


class ExecutionAudit(BaseModel):
    """Future interface — Business OS 1.5+. No runtime behavior."""
    audit_id: str
    plan_id: str
    results: list[ExecutionResult] = Field(default_factory=list)
    success_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    findings: list[str] = Field(default_factory=list)
    versions: KnowledgeVersionMetadata = Field(default_factory=KnowledgeVersionMetadata)
