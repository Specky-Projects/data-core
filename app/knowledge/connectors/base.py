"""Universal Connector Contract — every source exposes this interface.

The platform never depends on a specific source. All connectors implement:
  Fetch → Normalize → Extract Entities → Extract Evidence
  → Generate Metadata → Publish Canonical Knowledge

No wall-clock in pipeline logic. All timestamps anchor to EvaluationContext.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.adaptive_intelligence.dto import EvaluationContext
from app.knowledge.dto import (
    EntityCandidate,
    KnowledgeEvidence,
    KnowledgeItem,
    KnowledgeProvenance,
    KnowledgeSource,
    KnowledgeVersionMetadata,
    SourceType,
    _EPOCH,
    build_evidence_id,
    build_item_id,
    build_knowledge_provenance,
    compute_knowledge_freshness,
)


@dataclass
class RawItem:
    """Source-specific raw payload. Opaque outside the connector."""
    data: dict[str, Any]
    fetched_at: datetime = field(default_factory=lambda: _EPOCH)


@dataclass
class NormalizedItem:
    """Source-agnostic normalized representation. Produced by each connector."""
    title: str
    url: str
    summary: str
    content: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
    engagement: float = 0.0
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorResult:
    """Full result from a connector fetch pass."""
    source: KnowledgeSource
    raw_items: list[RawItem]
    fetched_at: datetime
    fetch_metadata: dict[str, Any] = field(default_factory=dict)


class AbstractKnowledgeConnector(ABC):
    """Universal connector contract.

    Subclasses implement the source-specific steps.
    The `ingest()` orchestration method is final — it calls the steps in order
    and builds the canonical KnowledgeItem. Subclasses must NOT override ingest().
    """

    connector_name: str = "abstract"
    source_type: SourceType = SourceType.UNKNOWN

    def ingest(self, evaluation_context: EvaluationContext) -> list[KnowledgeItem]:
        """Full pipeline: Fetch → Normalize → Extract → Build canonical items."""
        result = self.fetch(evaluation_context)
        items: list[KnowledgeItem] = []
        for raw in result.raw_items:
            try:
                normalized = self.normalize(raw)
                entity_candidates = self.extract_entities(normalized)
                evidence = self.extract_evidence(normalized, result.source)
                metadata = self.generate_metadata(normalized)
                item = self._build_canonical(
                    normalized, entity_candidates, evidence, metadata,
                    result.source, evaluation_context,
                )
                items.append(item)
            except Exception:
                continue
        return items

    @abstractmethod
    def fetch(self, evaluation_context: EvaluationContext) -> ConnectorResult:
        """Retrieve raw items from the source.

        Must not use datetime.now(). If timestamps are needed, use
        evaluation_context.evaluation_timestamp.
        """

    @abstractmethod
    def normalize(self, raw: RawItem) -> NormalizedItem:
        """Convert source-specific raw payload to NormalizedItem."""

    @abstractmethod
    def extract_entities(self, item: NormalizedItem) -> list[EntityCandidate]:
        """Extract entity candidates from a normalized item."""

    @abstractmethod
    def extract_evidence(self, item: NormalizedItem, source: KnowledgeSource) -> list[KnowledgeEvidence]:
        """Extract evidence fragments from a normalized item."""

    @abstractmethod
    def generate_metadata(self, item: NormalizedItem) -> dict[str, Any]:
        """Generate source-specific metadata dict."""

    def _build_canonical(
        self,
        normalized: NormalizedItem,
        entity_candidates: list[EntityCandidate],
        evidence: list[KnowledgeEvidence],
        metadata: dict[str, Any],
        source: KnowledgeSource,
        evaluation_context: EvaluationContext,
    ) -> KnowledgeItem:
        from app.knowledge.entity_resolution import resolve_entities

        item_id = build_item_id(normalized.url, source.source_id)
        provenance = build_knowledge_provenance(
            source_id=source.source_id,
            connector_name=self.connector_name,
            evaluation_context=evaluation_context,
            evidence_ids=[e.evidence_id for e in evidence],
            published_at=normalized.published_at,
            entity_lineage=[c.raw_name for c in entity_candidates[:10]],
        )
        freshness = compute_knowledge_freshness(
            published_at=normalized.published_at,
            evaluation_context=evaluation_context,
        )
        entities = resolve_entities(entity_candidates, source.source_id, evidence)
        confidence = min(1.0, 0.3 + 0.1 * len(entities) + 0.05 * min(5, len(evidence)))

        return KnowledgeItem(
            item_id=item_id,
            title=normalized.title[:512],
            summary=normalized.summary[:1024],
            url=normalized.url,
            content=normalized.content,
            author=normalized.author,
            source=source,
            entities=entities,
            evidence=evidence,
            topics=list({t.lower() for t in normalized.tags if t}),
            tags=normalized.tags,
            provenance=provenance,
            freshness=freshness,
            confidence=round(confidence, 4),
            engagement_score=normalized.engagement,
            published_at=normalized.published_at,
            metadata={**metadata, "connector": self.connector_name},
            versions=KnowledgeVersionMetadata(),
        )
