"""Research Opportunity Emitter.

Adapts the Research Lab's already-computed ``OpportunityRecord`` (poupi-crypto,
``app/research_lab/contracts.py``) into ``business_os.contracts.Opportunity``.

Pure format adaptation: every scientific value (``confidence``,
``scientific_score``, ``regimes_valid``, ``assets_valid``) is passed through
verbatim. Nothing is recomputed, and the Research Lab's own module is never
imported or altered — this module only accepts the raw dict shape it already
produces, matching the pattern already used by the Universal Platform
adapters (``AffiliateAdapter``, ``PoupiBabyAdapter``).
"""
from __future__ import annotations

from typing import Any

from app.business_os.contracts import (
    DomainKind,
    Opportunity,
    OpportunitySignal,
    OpportunityStatus,
)

# Research Lab's own PromotionStatus taxonomy (poupi-crypto/app/research_lab/
# contracts.py), mirrored here as plain strings to avoid a cross-repo import —
# research_lab is never imported or altered by this adapter.
_PROMOTION_TO_OPPORTUNITY_STATUS: dict[str, OpportunityStatus] = {
    "DRAFT": OpportunityStatus.DISCOVERED,
    "CANDIDATE": OpportunityStatus.DISCOVERED,
    "SCIENTIFIC_APPROVED": OpportunityStatus.EVALUATED,
    "COMMITTEE_PREVIEW": OpportunityStatus.APPROVED,
    "PROMOTED": OpportunityStatus.EXECUTING,
    "REJECTED": OpportunityStatus.REJECTED,
}


def _map_status(promotion_status: Any) -> OpportunityStatus:
    return _PROMOTION_TO_OPPORTUNITY_STATUS.get(
        str(promotion_status or "CANDIDATE").upper(), OpportunityStatus.DISCOVERED
    )


def build_opportunity_from_research(raw: dict[str, Any]) -> Opportunity:
    """Adapt a Research Lab ``OpportunityRecord`` dict into an ``Opportunity``.

    ``raw`` is the already-serialized output of ``OpportunityRecord`` — no
    field is recalculated, only renamed/repackaged into the canonical shape.
    """
    opportunity_id = str(raw["opportunity_id"])
    confidence = float(raw.get("confidence", 0.0))
    created_at = str(raw.get("created_at") or "")

    signals: list[OpportunitySignal] = []
    for regime in raw.get("regimes_valid") or ():
        signals.append(
            OpportunitySignal(
                signal_id=f"{opportunity_id}:regime:{regime}",
                source="research_lab.regimes_valid",
                strength=confidence,
                captured_at=created_at,
            )
        )
    for asset in raw.get("assets_valid") or ():
        signals.append(
            OpportunitySignal(
                signal_id=f"{opportunity_id}:asset:{asset}",
                source="research_lab.assets_valid",
                strength=confidence,
                captured_at=created_at,
            )
        )

    return Opportunity(
        opportunity_id=opportunity_id,
        domain=DomainKind.CRYPTO,
        status=_map_status(raw.get("promotion_status")),
        signals=tuple(signals),
        confidence=confidence,
        expected_value=raw.get("scientific_score"),
        discovered_at=created_at,
        pipeline_ref="research_lab.opportunity_discovery",
        evidence_refs=tuple(
            str(v)
            for v in (raw.get("experiment_id"), raw.get("hypothesis_id"), raw.get("scientific_id"))
            if v
        ),
        metadata={
            "title": raw.get("title"),
            "description": raw.get("description"),
            "feature_set": list(raw.get("feature_set") or ()),
            "promotion_status": raw.get("promotion_status"),
            "committee_preview": raw.get("committee_preview"),
        },
    )
