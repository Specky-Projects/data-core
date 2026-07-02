"""Poupi Baby runtime -> Business OS Opportunity bridge.

This observes real Poupi Baby commercial outputs and emits canonical Business
OS Opportunities through the existing Phase 1 emitter. It is deliberately
read-only against Poupi Baby: no publish call, no flag change, no re-ranking.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.business_os.opportunity_emitters import (
    OpportunityRegistry,
    build_opportunity_from_poupi_baby,
    emit_opportunity,
)
from app.business_os.poupi_baby_bridge.storage import JsonlOpportunityEvidenceRegistry
from app.universal_platform.adapters.poupi_baby_opportunity_adapter import (
    PoupiBabyOpportunityAdapter,
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _score_to_confidence(payload: dict[str, Any]) -> float:
    for key in ("confidence", "score"):
        if payload.get(key) is not None:
            value = float(payload[key])
            return value / 100.0 if value > 1 else value
    if payload.get("dealScore") is not None:
        return float(payload["dealScore"]) / 100.0
    return 0.0


def normalize_poupi_runtime_payload(
    payload: dict[str, Any],
    *,
    observed_at: str | None = None,
) -> dict[str, Any]:
    timestamp = observed_at or str(
        payload.get("discovered_at")
        or payload.get("discoveredAt")
        or payload.get("publishedAt")
        or payload.get("createdAt")
        or _utc_now()
    )
    opportunity_id = str(
        payload.get("id")
        or payload.get("opportunityId")
        or payload.get("offerId")
        or payload.get("productId")
    )
    evidence = payload.get("evidence") or [
        {
            "kind": "deal_score",
            "value": payload.get("dealScore", payload.get("score", "")),
            "weight": _score_to_confidence(payload),
        },
        {
            "kind": "url",
            "value": payload.get("affiliateUrl") or payload.get("productUrl") or "",
            "weight": 1.0,
        },
    ]
    source_ids = payload.get("sourceIds")
    if source_ids is None:
        source_ids = [payload["marketplace"]] if payload.get("marketplace") else []
    return {
        "id": opportunity_id,
        "verticalId": payload.get("verticalId") or payload.get("category"),
        "assetId": payload.get("assetId") or payload.get("productId"),
        "sourceIds": source_ids,
        "title": payload.get("title") or payload.get("productTitle") or payload.get("product"),
        "summary": payload.get("summary") or payload.get("messageSummary") or payload.get("dealLabel"),
        "confidence": _score_to_confidence(payload),
        "estimatedRoi": payload.get("estimatedRoi"),
        "estimatedMarketSize": payload.get("estimatedMarketSize"),
        "competitionScore": payload.get("competitionScore"),
        "complexityScore": payload.get("complexityScore"),
        "priority": payload.get("priority"),
        "discovered_at": timestamp,
        "evidence": evidence,
        "status": payload.get("status") or "active",
        "runtime": {
            "source": "poupi-baby",
            "dealScore": payload.get("dealScore"),
            "score": payload.get("score"),
            "category": payload.get("category"),
            "marketplace": payload.get("marketplace"),
            "productUrl": payload.get("productUrl"),
            "affiliateUrl": payload.get("affiliateUrl") or payload.get("affiliate_url"),
            "telegramStatus": payload.get("telegramStatus"),
            "siteStatus": payload.get("siteStatus"),
            "dryRun": payload.get("dryRun"),
        },
    }


class PoupiBabyOpportunityBridge:
    def __init__(
        self,
        evidence_registry: JsonlOpportunityEvidenceRegistry | None = None,
        opportunity_registry: OpportunityRegistry | None = None,
    ) -> None:
        self.evidence_registry = evidence_registry or JsonlOpportunityEvidenceRegistry()
        self.opportunity_registry = opportunity_registry or OpportunityRegistry()
        self.adapter = PoupiBabyOpportunityAdapter()

    def emit(
        self,
        payload: dict[str, Any],
        *,
        observed_at: str | None = None,
        planned_channels: tuple[str, ...] = ("site", "telegram"),
    ) -> dict[str, Any]:
        raw = normalize_poupi_runtime_payload(payload, observed_at=observed_at)
        emission = emit_opportunity(
            adapter=self.adapter,
            registry=self.opportunity_registry,
            raw=raw,
            build_opportunity=build_opportunity_from_poupi_baby,
            build_opportunity_kwargs={"discovered_at": raw["discovered_at"]},
        )
        runtime = raw.get("runtime") or {}
        persisted = {
            "record_type": "poupi_baby_opportunity_cycle",
            "persisted_at": _utc_now(),
            "source": "poupi-baby",
            "domain": emission.opportunity.domain.value,
            "status": emission.opportunity.status.value,
            "opportunity": _jsonable(emission.opportunity),
            "raw_payload": _jsonable(payload),
            "normalized_payload": _jsonable(raw),
            "references": {
                "lineage": emission.lineage_id,
                "evaluation_bundle": emission.registration.evaluation.bundle_id,
                "ranking_score": emission.registration.ranking.ranking_id,
                "business_snapshot": emission.registration.snapshot.snapshot_id,
                "replay": emission.registration.evaluation.replay_ref,
                "explainability": emission.registration.evaluation.explainability_ref,
                "audit_snapshot": emission.observation.audit.snapshot_id,
            },
            "observation": emission.observation.as_dict(),
            "registration": {
                "evaluation": _jsonable(emission.registration.evaluation),
                "ranking": _jsonable(emission.registration.ranking),
                "snapshot": _jsonable(emission.registration.snapshot),
            },
            "channels": {
                "planned": list(planned_channels),
                "site": runtime.get("siteStatus") or "unknown",
                "telegram": runtime.get("telegramStatus") or "unknown",
                "dry_run": runtime.get("dryRun"),
            },
            "publish_plan": {
                "mode": "observe_only",
                "site": "read_existing_status_only",
                "telegram": "read_existing_status_only",
            },
        }
        self.evidence_registry.append(persisted)
        return persisted

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.evidence_registry.list_recent(limit)


def emit_poupi_baby_runtime_opportunity(
    payload: dict[str, Any],
    *,
    observed_at: str | None = None,
    registry: JsonlOpportunityEvidenceRegistry | None = None,
) -> dict[str, Any]:
    return PoupiBabyOpportunityBridge(registry).emit(payload, observed_at=observed_at)
