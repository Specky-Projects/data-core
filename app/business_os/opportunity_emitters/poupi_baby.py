"""Poupi Baby Opportunity Emitter.

Adapts the already-existing Poupi Baby ``Opportunity`` record (TypeScript,
``poupi-baby/backend/src/business-os/platform/canonical-model.ts``) into
``business_os.contracts.Opportunity``. The TS type is Poupi Baby's own local
model — this module converts its serialized (JSON) form into the Business OS
canonical contract; it never recomputes ``confidence``, ``estimatedRoi``,
``priority`` or any other already-known value, and it never touches Poupi
Baby's own discovery engine (``opportunity-discovery-engine.service.ts``).

The existing ``PoupiBabyAdapter`` (``universal_platform/adapters/
poupi_baby_adapter.py``) remains solely responsible for lifecycle telemetry;
this module is the separate business-contract emitter requested for this
phase.
"""
from __future__ import annotations

from typing import Any

from app.business_os.contracts import (
    DomainKind,
    Opportunity,
    OpportunitySignal,
    OpportunityStatus,
)

# Poupi Baby's own PlatformLifecycle taxonomy (canonical-model.ts), mirrored as
# plain strings — no cross-repo import, poupi-baby is never altered.
_LIFECYCLE_TO_OPPORTUNITY_STATUS: dict[str, OpportunityStatus] = {
    "draft": OpportunityStatus.DISCOVERED,
    "active": OpportunityStatus.EVALUATED,
    "scaling": OpportunityStatus.EXECUTING,
    "paused": OpportunityStatus.APPROVED,
    "sunsetting": OpportunityStatus.CLOSED,
    "archived": OpportunityStatus.CLOSED,
}


def _map_status(lifecycle_status: Any) -> OpportunityStatus:
    return _LIFECYCLE_TO_OPPORTUNITY_STATUS.get(
        str(lifecycle_status or "draft").lower(), OpportunityStatus.DISCOVERED
    )


def build_opportunity_from_poupi_baby(
    raw: dict[str, Any],
    *,
    discovered_at: str,
    domain: DomainKind = DomainKind.AFFILIATE,
) -> Opportunity:
    """Adapt a Poupi Baby ``Opportunity`` (canonical-model.ts) dict into an
    ``Opportunity``.

    ``raw`` is the already-serialized output of Poupi Baby's discovery engine.
    ``discovered_at`` is required because the TS ``Opportunity`` interface
    carries no timestamp of its own; the caller supplies the moment the
    record was read (e.g. from the surrounding discovery run).
    """
    opportunity_id = str(raw["id"])
    confidence = float(raw.get("confidence", 0.0))
    evidence = raw.get("evidence") or []

    signals = tuple(
        OpportunitySignal(
            signal_id=f"{opportunity_id}:evidence:{idx}",
            source=f"poupi_baby.{item.get('kind', 'other')}",
            strength=(
                float(item["weight"]) if item.get("weight") is not None else confidence
            ),
            captured_at=discovered_at,
        )
        for idx, item in enumerate(evidence)
    )

    return Opportunity(
        opportunity_id=opportunity_id,
        domain=domain,
        status=_map_status(raw.get("status")),
        signals=signals,
        confidence=confidence,
        expected_value=raw.get("estimatedRoi"),
        discovered_at=discovered_at,
        pipeline_ref="poupi_baby.opportunity_discovery",
        evidence_refs=tuple(
            f"{item.get('kind', 'other')}:{item.get('value', '')}" for item in evidence
        ),
        metadata={
            "title": raw.get("title"),
            "summary": raw.get("summary"),
            "verticalId": raw.get("verticalId"),
            "assetId": raw.get("assetId"),
            "sourceIds": raw.get("sourceIds"),
            "estimatedMarketSize": raw.get("estimatedMarketSize"),
            "competitionScore": raw.get("competitionScore"),
            "complexityScore": raw.get("complexityScore"),
            "priority": raw.get("priority"),
            "lifecycle_status": raw.get("status"),
        },
    )
