"""Research Opportunity Adapter — Business OS 6.0 Phase 1.

Observes Research Lab ``OpportunityRecord`` emissions (poupi-crypto,
``app/research_lab/opportunity_discovery.py``) and normalises them into a
``UniversalEvent``, giving every emitted Opportunity automatic Replay,
Explainability, Learning Feed and Runtime Snapshot coverage through the
existing ``UniversalObservationRuntime``. Research Lab's own scoring and
discovery logic is never touched — only observed.
"""
from __future__ import annotations

from typing import Any

from app.universal_platform.adapters.base import BaseAdapter
from app.universal_platform.events import Severity, UniversalEvent


class ResearchOpportunityAdapter(BaseAdapter):
    PROJECT = "poupi-crypto-research-lab"
    DOMAIN = "CRYPTO"

    def to_event(self, raw: dict[str, Any]) -> UniversalEvent:
        return UniversalEvent.create(
            project=self.PROJECT,
            domain=self.DOMAIN,
            event_type="opportunity.discovered",
            entity_id=str(raw.get("opportunity_id") or "UNKNOWN"),
            occurred_at=str(raw.get("created_at") or ""),
            confidence=raw.get("confidence", 1.0),
            severity=Severity.INFO,
            evidence=[
                {
                    "evidence_id": raw.get("experiment_id"),
                    "source_type": "EXPERIMENT",
                    "source_name": "research_lab",
                },
                {
                    "evidence_id": raw.get("hypothesis_id"),
                    "source_type": "HYPOTHESIS",
                    "source_name": "research_lab",
                },
            ]
            if raw.get("experiment_id") or raw.get("hypothesis_id")
            else (),
            metrics={
                k: raw[k]
                for k in ("scientific_score", "promotion_status")
                if k in raw
            },
        )
