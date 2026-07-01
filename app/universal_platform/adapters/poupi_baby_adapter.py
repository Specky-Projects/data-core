"""WS1 — Poupi Baby Adapter.

Observes Poupi Baby lifecycle events (discovery → plan → content → publication
→ experiment → result) without touching the Opportunity Engine, Planner,
Reviewer, Runtime or Executor. Every event becomes an ObservationContract via
the shared runtime; nothing is decided or executed here.
"""
from __future__ import annotations

from typing import Any

from app.universal_platform.adapters.base import BaseAdapter
from app.universal_platform.events import Severity, UniversalEvent

# Poupi Baby lifecycle event types the adapter recognises. Everything maps to a
# GENERIC observation with INFO severity — Baby is recommendation-only.
BABY_EVENT_TYPES = (
    "opportunity.discovered",
    "plan.created",
    "article.generated",
    "image.created",
    "publication.done",
    "experiment.completed",
    "result.measured",
)


class PoupiBabyAdapter(BaseAdapter):
    PROJECT = "poupi-baby"
    DOMAIN = "POUPI_BABY"

    def to_event(self, raw: dict[str, Any]) -> UniversalEvent:
        event_type = str(raw.get("event_type") or "opportunity.discovered")
        entity_id = str(
            raw.get("entity_id")
            or raw.get("product")
            or raw.get("opportunity_id")
            or raw.get("candidate_id")
            or "UNKNOWN"
        )
        occurred_at = str(
            raw.get("occurred_at")
            or raw.get("discovered_at")
            or raw.get("decided_at")
            or ""
        )
        return UniversalEvent.create(
            project=self.PROJECT,
            domain=self.DOMAIN,
            event_type=event_type,
            entity_id=entity_id,
            occurred_at=occurred_at,
            confidence=raw.get("confidence", 1.0),
            severity=raw.get("severity", Severity.INFO),
            evidence=raw.get("evidence", ()),
            metrics={
                k: raw[k]
                for k in ("expected_value", "category", "score", "impressions", "conversions")
                if k in raw
            },
            payload=dict(raw),
            outcome=raw.get("outcome"),
            metadata={"lifecycle": event_type},
        )
