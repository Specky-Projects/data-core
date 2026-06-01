"""
app/real_estate/enrichment.py — Field enrichment job for direct_agencies raw collections.

Reads every real_estate / direct_agencies RawCollection, runs the light extractor,
and writes the result back as a `structured_fields` key in raw_json — WITHOUT
touching any of the original keys (raw_data, raw_html_snippet, strategy, etc.).

PostgreSQL JSONB update:
    raw_json = raw_json || '{"structured_fields": {...}}'::jsonb

Idempotent: re-running overwrites structured_fields but never the original data.

Returns:
    EnrichmentResult with per-agency stats and overall completeness metrics.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.raw.models import RawCollection
from app.real_estate.extractor import (
    _COMPLETENESS_FIELDS,
    completeness_score,
    extract_structured_fields,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AgencyStats:
    agency_id: str
    total: int = 0
    enriched: int = 0
    high_confidence: int = 0
    medium_confidence: int = 0
    low_confidence: int = 0
    price_present: int = 0
    title_present: int = 0
    neighborhood_present: int = 0
    listing_type_present: int = 0
    property_type_present: int = 0
    city_present: int = 0
    completeness_sum: float = 0.0

    @property
    def completeness_pct(self) -> float:
        if self.total == 0:
            return 0.0
        return round(100.0 * self.completeness_sum / self.total, 1)

    @property
    def price_coverage_pct(self) -> float:
        return round(100.0 * self.price_present / self.total, 1) if self.total else 0.0

    @property
    def title_coverage_pct(self) -> float:
        return round(100.0 * self.title_present / self.total, 1) if self.total else 0.0

    @property
    def neighborhood_coverage_pct(self) -> float:
        return round(100.0 * self.neighborhood_present / self.total, 1) if self.total else 0.0


@dataclass
class EnrichmentResult:
    total_records: int = 0
    enriched: int = 0
    errors: int = 0
    skipped: int = 0
    duration_ms: int = 0
    agency_stats: dict[str, AgencyStats] = field(default_factory=dict)
    overall_completeness_pct: float = 0.0
    timestamp: str = ""

    def summary(self) -> dict[str, Any]:
        return {
            "total_records": self.total_records,
            "enriched": self.enriched,
            "errors": self.errors,
            "skipped": self.skipped,
            "duration_ms": self.duration_ms,
            "overall_completeness_pct": self.overall_completeness_pct,
            "agency_stats": {
                aid: {
                    "total": s.total,
                    "completeness_pct": s.completeness_pct,
                    "price_coverage_pct": s.price_coverage_pct,
                    "title_coverage_pct": s.title_coverage_pct,
                    "neighborhood_coverage_pct": s.neighborhood_coverage_pct,
                    "high_confidence": s.high_confidence,
                    "medium_confidence": s.medium_confidence,
                    "low_confidence": s.low_confidence,
                }
                for aid, s in self.agency_stats.items()
            },
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Core enrichment
# ---------------------------------------------------------------------------

def run_field_enrichment(db: Session, *, batch_size: int = 500) -> EnrichmentResult:
    """Extract and write structured_fields for all direct_agencies records.

    Uses a raw SQL JSONB merge so the update is atomic per row and avoids
    loading full ORM objects into memory.

    Parameters
    ----------
    db:
        Active SQLAlchemy session (caller controls lifecycle).
    batch_size:
        Number of rows processed per commit cycle.
    """
    import time
    started = time.monotonic()

    result = EnrichmentResult(timestamp=datetime.now(timezone.utc).isoformat())

    # Fetch all direct_agencies records (raw_json as dict already)
    rows = (
        db.query(RawCollection.id, RawCollection.raw_json)
        .filter(
            RawCollection.module == "real_estate",
            RawCollection.source_name == "direct_agencies",
        )
        .all()
    )

    result.total_records = len(rows)
    if not rows:
        logger.info("real_estate.enrichment: no records found — nothing to do")
        return result

    batch_updates: list[dict[str, Any]] = []
    completeness_accumulator: float = 0.0

    for row_id, raw_json in rows:
        payload: dict[str, Any]
        if isinstance(raw_json, dict):
            payload = raw_json
        elif isinstance(raw_json, str):
            try:
                payload = json.loads(raw_json)
            except json.JSONDecodeError:
                result.errors += 1
                continue
        else:
            result.errors += 1
            continue

        try:
            sf = extract_structured_fields(payload)
        except Exception as exc:
            logger.warning(
                "real_estate.enrichment: extraction error",
                extra={"row_id": str(row_id), "error": str(exc)},
            )
            result.errors += 1
            continue

        cs = completeness_score(sf)
        completeness_accumulator += cs

        # Per-agency stats
        aid = sf.get("agency_id") or payload.get("agency_id", "unknown")
        if aid not in result.agency_stats:
            result.agency_stats[aid] = AgencyStats(agency_id=aid)
        stats = result.agency_stats[aid]
        stats.total += 1
        stats.enriched += 1
        stats.completeness_sum += cs

        conf = sf.get("extraction_confidence", "low")
        if conf == "high":
            stats.high_confidence += 1
        elif conf == "medium":
            stats.medium_confidence += 1
        else:
            stats.low_confidence += 1

        if sf.get("price") is not None:
            stats.price_present += 1
        if sf.get("title"):
            stats.title_present += 1
        if sf.get("neighborhood"):
            stats.neighborhood_present += 1
        if sf.get("listing_type"):
            stats.listing_type_present += 1
        if sf.get("property_type"):
            stats.property_type_present += 1
        if sf.get("city"):
            stats.city_present += 1

        batch_updates.append({"id": str(row_id), "sf": json.dumps(sf, ensure_ascii=False, default=str)})
        result.enriched += 1

        # Commit in batches
        if len(batch_updates) >= batch_size:
            _flush_batch(db, batch_updates)
            batch_updates.clear()

    if batch_updates:
        _flush_batch(db, batch_updates)

    if result.total_records > 0:
        result.overall_completeness_pct = round(
            100.0 * completeness_accumulator / result.total_records, 1
        )

    result.duration_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "real_estate.enrichment: complete",
        extra=result.summary(),
    )
    return result


def _flush_batch(db: Session, updates: list[dict[str, Any]]) -> None:
    """Write structured_fields via JSONB merge for a batch of rows."""
    for item in updates:
        db.execute(
            text(
                "UPDATE raw_collections "
                "SET raw_json = raw_json || jsonb_build_object('structured_fields', CAST(:sf AS jsonb)) "
                "WHERE id = CAST(:id AS uuid)"
            ),
            {"id": item["id"], "sf": item["sf"]},
        )
    db.commit()
