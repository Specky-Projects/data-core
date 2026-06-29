"""Hacker News Knowledge Connector — Priority 1.

Uses the public Firebase HN API. No auth required.
Fetches top/new/ask/show stories and normalizes to KnowledgeItem.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from app.adaptive_intelligence.dto import EvaluationContext
from app.knowledge.connectors.base import (
    AbstractKnowledgeConnector,
    ConnectorResult,
    NormalizedItem,
    RawItem,
)
from app.knowledge.dto import (
    EntityCandidate,
    EntityType,
    KnowledgeEvidence,
    KnowledgeSource,
    SourceType,
    _EPOCH,
    build_evidence_id,
)

logger = logging.getLogger(__name__)

_HN_API = "https://hacker-news.firebaseio.com/v0"
_HN_WEB = "https://news.ycombinator.com/item?id="


class HackerNewsConnector(AbstractKnowledgeConnector):
    """Fetches top stories from Hacker News Firebase API."""

    connector_name = "hacker_news"
    source_type = SourceType.HACKER_NEWS

    def __init__(
        self,
        story_type: str = "topstories",
        max_items: int = 20,
        _raw_override: list[dict[str, Any]] | None = None,
    ) -> None:
        self.story_type = story_type
        self.max_items = max_items
        self._raw_override = _raw_override

    def fetch(self, evaluation_context: EvaluationContext) -> ConnectorResult:
        source = KnowledgeSource(
            source_id="hacker_news",
            source_type=SourceType.HACKER_NEWS,
            url=_HN_API,
            name="Hacker News",
        )
        if self._raw_override is not None:
            raws = [RawItem(data=d, fetched_at=evaluation_context.evaluation_timestamp) for d in self._raw_override]
            return ConnectorResult(source=source, raw_items=raws, fetched_at=evaluation_context.evaluation_timestamp)

        raw_items: list[RawItem] = []
        try:
            url = f"{_HN_API}/{self.story_type}.json"
            with urllib.request.urlopen(url, timeout=10) as resp:
                ids = json.loads(resp.read().decode())[: self.max_items]

            for story_id in ids:
                try:
                    item_url = f"{_HN_API}/item/{story_id}.json"
                    with urllib.request.urlopen(item_url, timeout=5) as resp:
                        story = json.loads(resp.read().decode())
                        if story and story.get("type") == "story":
                            raw_items.append(RawItem(
                                data=story,
                                fetched_at=evaluation_context.evaluation_timestamp,
                            ))
                except Exception as exc:
                    logger.debug("hn item %s error: %s", story_id, exc)
        except (urllib.error.URLError, Exception) as exc:
            logger.warning("hn fetch error: %s", exc)

        return ConnectorResult(
            source=source,
            raw_items=raw_items,
            fetched_at=evaluation_context.evaluation_timestamp,
        )

    def normalize(self, raw: RawItem) -> NormalizedItem:
        d = raw.data
        published_at: datetime | None = None
        ts = d.get("time")
        if ts:
            try:
                published_at = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            except (ValueError, OSError):
                pass

        story_url = d.get("url", f"{_HN_WEB}{d.get('id', '')}")
        title = d.get("title", "Untitled")
        text = d.get("text", "") or ""
        summary = text[:400] if text else title

        score = d.get("score", 0)
        descendants = d.get("descendants", 0)
        engagement = min(1.0, (score + descendants * 3) / 1000.0)

        tags: list[str] = []
        if d.get("type"):
            tags.append(d["type"])

        return NormalizedItem(
            title=title[:512],
            url=story_url,
            summary=summary,
            content=text or None,
            author=d.get("by"),
            published_at=published_at,
            tags=tags,
            engagement=engagement,
            raw_data=d,
        )

    def extract_entities(self, item: NormalizedItem) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        title = item.title.lower()

        tech_keywords = [
            "python", "rust", "go", "typescript", "javascript", "llm", "gpt", "ai",
            "ml", "kubernetes", "docker", "postgres", "redis", "react", "vue",
            "linux", "macos", "windows", "aws", "gcp", "azure",
        ]
        for kw in tech_keywords:
            if kw in title:
                candidates.append(EntityCandidate(
                    raw_name=kw,
                    entity_type=EntityType.TECHNOLOGY,
                    context=item.title,
                    confidence=0.7,
                ))

        author = item.raw_data.get("by")
        if author:
            candidates.append(EntityCandidate(
                raw_name=author,
                entity_type=EntityType.PERSON,
                context="HN story author",
                confidence=0.6,
            ))

        return candidates

    def extract_evidence(self, item: NormalizedItem, source: KnowledgeSource) -> list[KnowledgeEvidence]:
        evidence: list[KnowledgeEvidence] = []
        d = item.raw_data
        ts = item.published_at or _EPOCH

        if item.title:
            evidence.append(KnowledgeEvidence(
                evidence_id=build_evidence_id(source.source_id, item.title, ts),
                content=item.title,
                source_id=source.source_id,
                item_url=item.url,
                weight=0.7,
                timestamp=ts,
                evidence_type="title",
            ))

        score = d.get("score", 0)
        if score:
            score_text = f"HN score: {score}"
            evidence.append(KnowledgeEvidence(
                evidence_id=build_evidence_id(source.source_id, score_text + item.url, ts),
                content=score_text,
                source_id=source.source_id,
                item_url=item.url,
                weight=min(1.0, score / 500.0),
                timestamp=ts,
                evidence_type="engagement_signal",
            ))

        return evidence

    def generate_metadata(self, item: NormalizedItem) -> dict[str, Any]:
        d = item.raw_data
        return {
            "hn_id": d.get("id"),
            "score": d.get("score", 0),
            "comments": d.get("descendants", 0),
            "author": d.get("by"),
            "story_type": d.get("type"),
        }
