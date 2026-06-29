"""GitHub Knowledge Connector — Priority 1.

Fetches trending repositories and topics from GitHub public API.
No auth required for basic reads (rate-limited to 60 req/hour).
All timestamps anchored to evaluation_context.evaluation_timestamp.
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

_GITHUB_API = "https://api.github.com"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "business-os/1.4",
}


class GitHubConnector(AbstractKnowledgeConnector):
    """Fetches trending/search results from GitHub public API."""

    connector_name = "github"
    source_type = SourceType.GITHUB

    def __init__(
        self,
        topics: list[str] | None = None,
        max_items: int = 20,
        _raw_override: list[dict[str, Any]] | None = None,
    ) -> None:
        self.topics = topics or ["python", "machine-learning", "ai"]
        self.max_items = max_items
        self._raw_override = _raw_override

    def fetch(self, evaluation_context: EvaluationContext) -> ConnectorResult:
        source = KnowledgeSource(
            source_id="github",
            source_type=SourceType.GITHUB,
            url=_GITHUB_API,
            name="GitHub",
        )
        if self._raw_override is not None:
            raws = [RawItem(data=d, fetched_at=evaluation_context.evaluation_timestamp) for d in self._raw_override]
            return ConnectorResult(source=source, raw_items=raws, fetched_at=evaluation_context.evaluation_timestamp)

        raw_items: list[RawItem] = []
        per_topic = max(1, self.max_items // len(self.topics))
        for topic in self.topics:
            try:
                url = f"{_GITHUB_API}/search/repositories?q=topic:{topic}&sort=stars&per_page={per_topic}"
                req = urllib.request.Request(url, headers=_HEADERS)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    for repo in data.get("items", [])[:per_topic]:
                        raw_items.append(RawItem(
                            data={**repo, "_topic": topic},
                            fetched_at=evaluation_context.evaluation_timestamp,
                        ))
            except (urllib.error.URLError, Exception) as exc:
                logger.warning("github fetch error for topic %s: %s", topic, exc)

        return ConnectorResult(
            source=source,
            raw_items=raw_items,
            fetched_at=evaluation_context.evaluation_timestamp,
        )

    def normalize(self, raw: RawItem) -> NormalizedItem:
        d = raw.data
        published_at: datetime | None = None
        pushed = d.get("pushed_at") or d.get("created_at")
        if pushed:
            try:
                published_at = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
            except ValueError:
                pass

        description = d.get("description") or ""
        topics = d.get("topics", [])
        if d.get("_topic") and d["_topic"] not in topics:
            topics = [d["_topic"]] + list(topics)
        lang = d.get("language") or ""
        if lang:
            topics = [lang.lower()] + topics

        stars = d.get("stargazers_count", 0)
        forks = d.get("forks_count", 0)
        engagement = min(1.0, (stars + forks * 2) / 10_000.0)

        return NormalizedItem(
            title=d.get("full_name", d.get("name", "unknown")),
            url=d.get("html_url", ""),
            summary=description[:500] if description else f"GitHub repository: {d.get('full_name', '')}",
            content=description or None,
            author=d.get("owner", {}).get("login"),
            published_at=published_at,
            tags=[t for t in topics[:10] if t],
            engagement=engagement,
            raw_data=d,
        )

    def extract_entities(self, item: NormalizedItem) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        d = item.raw_data

        candidates.append(EntityCandidate(
            raw_name=item.title,
            entity_type=EntityType.REPOSITORY,
            context=item.summary[:200],
            confidence=0.9,
        ))

        owner = d.get("owner", {}).get("login")
        if owner:
            candidates.append(EntityCandidate(
                raw_name=owner,
                entity_type=EntityType.PERSON,
                context="repository owner",
                confidence=0.8,
            ))

        lang = d.get("language")
        if lang:
            candidates.append(EntityCandidate(
                raw_name=lang,
                entity_type=EntityType.TECHNOLOGY,
                context="programming language",
                confidence=0.9,
            ))

        for topic in (d.get("topics") or [])[:5]:
            candidates.append(EntityCandidate(
                raw_name=topic,
                entity_type=EntityType.TOPIC,
                context="github topic",
                confidence=0.7,
            ))

        return candidates

    def extract_evidence(self, item: NormalizedItem, source: KnowledgeSource) -> list[KnowledgeEvidence]:
        evidence: list[KnowledgeEvidence] = []
        d = item.raw_data
        ts = item.published_at or _EPOCH

        if item.summary:
            evidence.append(KnowledgeEvidence(
                evidence_id=build_evidence_id(source.source_id, item.summary, ts),
                content=item.summary[:512],
                source_id=source.source_id,
                item_url=item.url,
                weight=0.8,
                timestamp=ts,
                evidence_type="description",
            ))

        stars = d.get("stargazers_count", 0)
        if stars:
            star_text = f"{stars} stars on GitHub"
            evidence.append(KnowledgeEvidence(
                evidence_id=build_evidence_id(source.source_id, star_text + item.url, ts),
                content=star_text,
                source_id=source.source_id,
                item_url=item.url,
                weight=min(1.0, stars / 5000.0),
                timestamp=ts,
                evidence_type="engagement_signal",
            ))

        return evidence

    def generate_metadata(self, item: NormalizedItem) -> dict[str, Any]:
        d = item.raw_data
        return {
            "stars": d.get("stargazers_count", 0),
            "forks": d.get("forks_count", 0),
            "watchers": d.get("watchers_count", 0),
            "open_issues": d.get("open_issues_count", 0),
            "language": d.get("language"),
            "license": (d.get("license") or {}).get("spdx_id"),
            "topics": d.get("topics", []),
        }
