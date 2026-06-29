"""Generic RSS/Atom Connector — Priority 1.

Parses any RSS 2.0 or Atom 1.0 feed URL.
All timestamps anchored to evaluation_context.evaluation_timestamp.
"""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
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

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _text(el: ET.Element | None, default: str = "") -> str:
    if el is None:
        return default
    return (el.text or "").strip()


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc) if raw.endswith("Z") and "%z" not in fmt else datetime.strptime(raw, fmt)
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(raw)
    except Exception:
        return None


class RSSConnector(AbstractKnowledgeConnector):
    """Generic RSS/Atom feed connector."""

    connector_name = "rss"
    source_type = SourceType.RSS

    def __init__(
        self,
        feed_url: str,
        feed_name: str = "",
        max_items: int = 20,
        _raw_override: list[dict[str, Any]] | None = None,
    ) -> None:
        self.feed_url = feed_url
        self.feed_name = feed_name or feed_url
        self.max_items = max_items
        self._raw_override = _raw_override

    def fetch(self, evaluation_context: EvaluationContext) -> ConnectorResult:
        source = KnowledgeSource(
            source_id=f"rss:{self.feed_url}",
            source_type=SourceType.RSS,
            url=self.feed_url,
            name=self.feed_name,
        )
        if self._raw_override is not None:
            raws = [RawItem(data=d, fetched_at=evaluation_context.evaluation_timestamp) for d in self._raw_override]
            return ConnectorResult(source=source, raw_items=raws, fetched_at=evaluation_context.evaluation_timestamp)

        raw_items: list[RawItem] = []
        try:
            req = urllib.request.Request(self.feed_url, headers={"User-Agent": "business-os/1.4"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="replace")
            root = ET.fromstring(content)
            items = self._parse_feed(root)
            for item in items[: self.max_items]:
                raw_items.append(RawItem(data=item, fetched_at=evaluation_context.evaluation_timestamp))
        except (urllib.error.URLError, ET.ParseError, Exception) as exc:
            logger.warning("rss fetch error %s: %s", self.feed_url, exc)

        return ConnectorResult(
            source=source,
            raw_items=raw_items,
            fetched_at=evaluation_context.evaluation_timestamp,
        )

    def _parse_feed(self, root: ET.Element) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        # RSS 2.0
        for item in root.findall(".//item"):
            items.append({
                "_format": "rss",
                "title": _text(item.find("title")),
                "link": _text(item.find("link")),
                "description": _text(item.find("description")),
                "pubDate": _text(item.find("pubDate")),
                "author": _text(item.find("author")) or _text(item.find("dc:creator", _NS)),
                "category": [_text(c) for c in item.findall("category")],
            })
        # Atom 1.0
        if not items:
            for entry in root.findall("atom:entry", _NS):
                link_el = entry.find("atom:link", _NS)
                link = link_el.get("href", "") if link_el is not None else ""
                items.append({
                    "_format": "atom",
                    "title": _text(entry.find("atom:title", _NS)),
                    "link": link,
                    "description": _text(entry.find("atom:summary", _NS)),
                    "pubDate": _text(entry.find("atom:published", _NS)) or _text(entry.find("atom:updated", _NS)),
                    "author": _text(entry.find(".//atom:name", _NS)),
                    "category": [c.get("term", "") for c in entry.findall("atom:category", _NS)],
                })
        return items

    def normalize(self, raw: RawItem) -> NormalizedItem:
        d = raw.data
        return NormalizedItem(
            title=(d.get("title") or "Untitled")[:512],
            url=d.get("link") or "",
            summary=(d.get("description") or "")[:500],
            content=d.get("description") or None,
            author=d.get("author") or None,
            published_at=_parse_date(d.get("pubDate")),
            tags=[c for c in (d.get("category") or []) if c],
            engagement=0.0,
            raw_data=d,
        )

    def extract_entities(self, item: NormalizedItem) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        for tag in item.tags[:5]:
            candidates.append(EntityCandidate(
                raw_name=tag,
                entity_type=EntityType.TOPIC,
                context="rss category",
                confidence=0.6,
            ))
        return candidates

    def extract_evidence(self, item: NormalizedItem, source: KnowledgeSource) -> list[KnowledgeEvidence]:
        evidence: list[KnowledgeEvidence] = []
        ts = item.published_at or _EPOCH
        if item.summary:
            evidence.append(KnowledgeEvidence(
                evidence_id=build_evidence_id(source.source_id, item.summary[:256], ts),
                content=item.summary[:512],
                source_id=source.source_id,
                item_url=item.url,
                weight=0.6,
                timestamp=ts,
                evidence_type="description",
            ))
        return evidence

    def generate_metadata(self, item: NormalizedItem) -> dict[str, Any]:
        return {
            "feed_url": self.feed_url,
            "feed_name": self.feed_name,
            "format": item.raw_data.get("_format", "rss"),
        }
