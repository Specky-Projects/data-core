"""WS4 — Affiliate Adapter.

Observes the monetisation project (clicks, conversions, revenue, campaigns,
products, commissions) and projects each into the scientific chain so revenue
facts feed Evidence → Learning Feed → Knowledge. The affiliate business logic
(attribution, payout) is never altered — only observed.
"""
from __future__ import annotations

from typing import Any

from app.scientific_consumers.facts import OutcomeFact
from app.universal_platform.adapters.base import BaseAdapter
from app.universal_platform.events import Severity, UniversalEvent

AFFILIATE_EVENT_TYPES = (
    "click",
    "conversion",
    "revenue",
    "campaign",
    "product",
    "commission",
)

# Monetary events carry a realized outcome so the learning feed activates.
_OUTCOME_EVENTS = {"conversion", "revenue", "commission"}


class AffiliateAdapter(BaseAdapter):
    PROJECT = "affiliate"
    DOMAIN = "AFFILIATE"

    def to_event(self, raw: dict[str, Any]) -> UniversalEvent:
        event_type = str(raw.get("event_type") or "click")
        entity_id = str(
            raw.get("entity_id")
            or raw.get("product_id")
            or raw.get("campaign_id")
            or raw.get("product")
            or "UNKNOWN"
        )
        occurred_at = str(raw.get("occurred_at") or raw.get("timestamp") or "")
        metrics = {
            k: raw[k]
            for k in ("clicks", "conversions", "revenue", "commission", "roi", "epc", "cvr")
            if k in raw
        }
        outcome = None
        base_type = event_type.split(".")[0]
        if base_type in _OUTCOME_EVENTS:
            realized = raw.get("revenue", raw.get("commission"))
            if realized is not None:
                outcome = OutcomeFact(
                    kind="SUCCESS" if float(realized) > 0 else "INCONCLUSIVE",
                    realized_value=float(realized),
                    expected_value=(
                        float(raw["expected_value"]) if raw.get("expected_value") is not None else None
                    ),
                    recorded_at=occurred_at,
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
            metrics=metrics,
            payload=dict(raw),
            outcome=outcome,
            metadata={"channel": raw.get("channel", "affiliate")},
        )
