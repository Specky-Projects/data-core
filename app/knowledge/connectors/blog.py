"""Generic Blog/HTTP Connector — Priority 1.

Fetches a generic web page, extracts title + body text via html.parser.
No external HTML parsing dependencies required.
"""

from __future__ import annotations

import html
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
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


class _TextExtractor(HTMLParser):
    """Minimal HTML → text extractor using stdlib html.parser."""

    _SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside"}

    def __init__(self) -> None:
        super().__init__()
        self._title = ""
        self._in_title = False
        self._skip_depth = 0
        self._current_skip: str | None = None
        self._texts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "title":
            self._in_title = True
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            self._current_skip = tag

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title and not self._title:
            self._title = html.unescape(text)
        elif self._skip_depth == 0:
            self._texts.append(html.unescape(text))

    @property
    def title(self) -> str:
        return self._title

    @property
    def body_text(self) -> str:
        return " ".join(self._texts)


class BlogConnector(AbstractKnowledgeConnector):
    """Generic blog/HTTP connector — fetches one or more URLs."""

    connector_name = "blog"
    source_type = SourceType.BLOG

    def __init__(
        self,
        urls: list[str],
        blog_name: str = "",
        max_content_chars: int = 2000,
        _raw_override: list[dict[str, Any]] | None = None,
    ) -> None:
        self.urls = urls
        self.blog_name = blog_name
        self.max_content_chars = max_content_chars
        self._raw_override = _raw_override

    def fetch(self, evaluation_context: EvaluationContext) -> ConnectorResult:
        base_url = self.urls[0] if self.urls else "https://example.com"
        source = KnowledgeSource(
            source_id=f"blog:{base_url}",
            source_type=SourceType.BLOG,
            url=base_url,
            name=self.blog_name or base_url,
        )
        if self._raw_override is not None:
            raws = [RawItem(data=d, fetched_at=evaluation_context.evaluation_timestamp) for d in self._raw_override]
            return ConnectorResult(source=source, raw_items=raws, fetched_at=evaluation_context.evaluation_timestamp)

        raw_items: list[RawItem] = []
        for url in self.urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "business-os/1.4"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    content = resp.read(1_048_576).decode("utf-8", errors="replace")
                parser = _TextExtractor()
                parser.feed(content)
                raw_items.append(RawItem(
                    data={
                        "url": url,
                        "html_title": parser.title,
                        "body_text": parser.body_text[: self.max_content_chars],
                    },
                    fetched_at=evaluation_context.evaluation_timestamp,
                ))
            except (urllib.error.URLError, Exception) as exc:
                logger.warning("blog fetch error %s: %s", url, exc)

        return ConnectorResult(
            source=source,
            raw_items=raw_items,
            fetched_at=evaluation_context.evaluation_timestamp,
        )

    def normalize(self, raw: RawItem) -> NormalizedItem:
        d = raw.data
        title = d.get("html_title") or d.get("url", "Untitled")
        body = (d.get("body_text") or "")[:500]
        return NormalizedItem(
            title=title[:512],
            url=d.get("url", ""),
            summary=body,
            content=d.get("body_text") or None,
            author=None,
            published_at=None,
            tags=[],
            engagement=0.0,
            raw_data=d,
        )

    def extract_entities(self, item: NormalizedItem) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        # Extract capitalized words as potential entity candidates
        text = f"{item.title} {item.summary}"
        words = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text)
        seen: set[str] = set()
        for word in words[:8]:
            if word.lower() not in seen:
                seen.add(word.lower())
                candidates.append(EntityCandidate(
                    raw_name=word,
                    entity_type=EntityType.UNKNOWN,
                    context=item.title,
                    confidence=0.4,
                ))
        return candidates

    def extract_evidence(self, item: NormalizedItem, source: KnowledgeSource) -> list[KnowledgeEvidence]:
        evidence: list[KnowledgeEvidence] = []
        ts = _EPOCH
        if item.summary:
            evidence.append(KnowledgeEvidence(
                evidence_id=build_evidence_id(source.source_id, item.summary[:256], ts),
                content=item.summary[:512],
                source_id=source.source_id,
                item_url=item.url,
                weight=0.5,
                timestamp=ts,
                evidence_type="body_text",
            ))
        return evidence

    def generate_metadata(self, item: NormalizedItem) -> dict[str, Any]:
        return {
            "blog_name": self.blog_name,
            "url": item.url,
            "content_length": len(item.content or ""),
        }
