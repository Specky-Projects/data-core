"""
app/real_estate/drift.py — Schema drift and field-presence detection for direct_agencies.

Computes per-agency metrics:
  field_presence_rate   — fraction of records where each key field is present (0–1)
  schema_drift_score    — 0–100, decreases when field coverage drops vs baseline

These metrics are written back into source_health.details_json and exposed via
Prometheus gauges (real_estate_field_presence_rate, real_estate_schema_drift_score).

Drift is flagged when field_presence_rate drops >20 percentage points vs the
running baseline stored in source_health.details_json['field_presence_baseline'].
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.raw.models import RawCollection

logger = logging.getLogger(__name__)

_TRACKED_FIELDS = ["title", "listing_type", "property_type", "price", "city", "neighborhood"]
_DRIFT_THRESHOLD = 0.20   # 20 pp drop triggers WARNING


@dataclass
class FieldPresenceReport:
    agency_id: str
    total: int = 0
    field_presence: dict[str, float] = field(default_factory=dict)  # field → rate 0–1
    schema_drift_score: float = 100.0
    drift_fields: list[str] = field(default_factory=list)          # fields that drifted
    baseline_used: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agency_id": self.agency_id,
            "total": self.total,
            "field_presence": self.field_presence,
            "schema_drift_score": self.schema_drift_score,
            "drift_fields": self.drift_fields,
            "baseline_used": self.baseline_used,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }


def compute_field_presence(
    db: Session,
    *,
    baseline: dict[str, dict[str, float]] | None = None,
) -> dict[str, FieldPresenceReport]:
    """Compute field presence rates from structured_fields for all agencies.

    Parameters
    ----------
    db:
        Active SQLAlchemy session.
    baseline:
        Dict of {agency_id: {field: rate}} from a previous run.
        Used to detect drift. If None, no drift comparison is performed.

    Returns
    -------
    Dict of agency_id → FieldPresenceReport
    """
    rows = (
        db.query(RawCollection.raw_json)
        .filter(
            RawCollection.module == "real_estate",
            RawCollection.source_name == "direct_agencies",
        )
        .all()
    )

    # Accumulate per-agency
    agency_counts: dict[str, dict[str, int]] = {}
    agency_total: dict[str, int] = {}

    for (raw_json,) in rows:
        payload: dict[str, Any]
        if isinstance(raw_json, dict):
            payload = raw_json
        elif isinstance(raw_json, str):
            try:
                payload = json.loads(raw_json)
            except json.JSONDecodeError:
                continue
        else:
            continue

        sf = payload.get("structured_fields")
        if not isinstance(sf, dict):
            continue  # not yet enriched

        aid = sf.get("agency_id") or payload.get("agency_id", "unknown")
        if aid not in agency_counts:
            agency_counts[aid] = {f: 0 for f in _TRACKED_FIELDS}
            agency_total[aid] = 0

        agency_total[aid] += 1
        for f in _TRACKED_FIELDS:
            val = sf.get(f)
            if val not in (None, "", [], 0):
                agency_counts[aid][f] += 1

    reports: dict[str, FieldPresenceReport] = {}

    for aid, counts in agency_counts.items():
        total = agency_total[aid]
        presence = {
            f: round(counts[f] / total, 3) if total else 0.0
            for f in _TRACKED_FIELDS
        }

        # Drift detection
        drift_fields: list[str] = []
        base = (baseline or {}).get(aid, {})
        if base:
            for f, rate in presence.items():
                base_rate = base.get(f, rate)  # no baseline → no drift
                if (base_rate - rate) > _DRIFT_THRESHOLD:
                    drift_fields.append(f)

        # Drift score: start at 100, subtract 15 per drifted field
        drift_score = max(0.0, 100.0 - len(drift_fields) * 15.0)

        if drift_fields:
            logger.warning(
                "real_estate.drift: field presence drop detected",
                extra={"agency": aid, "drift_fields": drift_fields, "drift_score": drift_score},
            )

        reports[aid] = FieldPresenceReport(
            agency_id=aid,
            total=total,
            field_presence=presence,
            schema_drift_score=drift_score,
            drift_fields=drift_fields,
            baseline_used=base,
        )

    return reports


def compute_dataset_drift_score(reports: dict[str, FieldPresenceReport]) -> float:
    """Aggregate drift score across all agencies (simple average)."""
    if not reports:
        return 100.0
    return round(sum(r.schema_drift_score for r in reports.values()) / len(reports), 1)
