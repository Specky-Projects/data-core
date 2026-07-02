"""Poupi Baby Opportunity Adapter — Business OS 6.0 Phase 1.

Observes Poupi Baby's discovered ``Opportunity`` records (TypeScript,
``poupi-baby/backend/src/business-os/platform/canonical-model.ts``) and
normalises them into a ``UniversalEvent``, giving every emitted Opportunity
automatic Replay, Explainability, Learning Feed and Runtime Snapshot coverage.

This is a separate adapter from ``PoupiBabyAdapter`` (lifecycle telemetry,
unchanged and untouched by this phase) — this one is the business-contract
emitter requested for Poupi Baby's discovered Opportunities specifically.
Poupi Baby's own discovery engine is never touched — only observed.
"""
from __future__ import annotations

from typing import Any

from app.universal_platform.adapters.base import BaseAdapter
from app.universal_platform.events import Severity, UniversalEvent


class PoupiBabyOpportunityAdapter(BaseAdapter):
    PROJECT = "poupi-baby"
    DOMAIN = "AFFILIATE"

    def to_event(self, raw: dict[str, Any]) -> UniversalEvent:
        evidence = raw.get("evidence") or []
        return UniversalEvent.create(
            project=self.PROJECT,
            domain=self.DOMAIN,
            event_type="opportunity.discovered",
            entity_id=str(raw.get("id") or "UNKNOWN"),
            occurred_at=str(raw.get("discovered_at") or raw.get("discoveredAt") or ""),
            confidence=raw.get("confidence", 1.0),
            severity=Severity.INFO,
            evidence=[
                {
                    "evidence_id": f"{item.get('kind', 'other')}:{item.get('value', '')}",
                    "source_type": str(item.get("kind", "other")).upper(),
                    "source_name": "poupi-baby",
                    "contribution_weight": item.get("weight"),
                }
                for item in evidence
            ],
            metrics={
                k: raw[k]
                for k in ("estimatedRoi", "estimatedMarketSize", "competitionScore", "complexityScore", "priority")
                if k in raw
            },
        )
