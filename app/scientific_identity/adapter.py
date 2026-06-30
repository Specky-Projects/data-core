"""ScientificIdentityAdapter — bridges legacy domain objects to ScientificIdentity.

Every adapter follows the pattern:
    Legacy Object → (Adapter) → ScientificIdentity

No legacy objects are modified. Adapters are pure functions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.scientific_identity.contract import (
    ScientificEntityType,
    ScientificIdentity,
    stable_hash,
)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ── SIP CanonicalDecisionRecord adapter ───────────────────────────────────────


def from_canonical_decision_record(record: Any) -> ScientificIdentity:
    """Adapt a SIP CanonicalDecisionRecord to ScientificIdentity.

    Assumes the record has: canonical_decision_id, lineage_id, decided_at,
    strategy (producer hint), decision_stage.
    """
    entity_type = _stage_to_entity_type(str(getattr(record, "decision_stage", "")))
    return ScientificIdentity(
        entity_type=entity_type,
        entity_id=str(record.canonical_decision_id),
        lineage_id=str(record.lineage_id),
        producer=f"sip/{getattr(record, 'strategy', 'unknown')}",
        produced_at=str(getattr(record, "decided_at", _now_iso())),
        parent_scientific_id=None,
        metadata={
            "decision_action": str(getattr(record, "decision_action", "")),
            "decision_reason_code": str(getattr(record, "decision_reason_code", "")),
            "symbol": str(getattr(record, "symbol", "")),
        },
    )


def _stage_to_entity_type(stage: str) -> ScientificEntityType:
    mapping = {
        "SIGNAL": ScientificEntityType.OBSERVATION,
        "CANDIDATE": ScientificEntityType.EVIDENCE,
        "PREVIEW": ScientificEntityType.PREVIEW,
        "COMMITTEE": ScientificEntityType.COMMITTEE,
        "RISK": ScientificEntityType.DECISION,
        "GUARDRAIL": ScientificEntityType.DECISION,
        "SIZING": ScientificEntityType.DECISION,
        "EXECUTION_GATE": ScientificEntityType.DECISION,
        "EXECUTION": ScientificEntityType.EXECUTION,
        "FILL": ScientificEntityType.EXECUTION,
        "CLOSE": ScientificEntityType.OUTCOME,
        "OUTCOME": ScientificEntityType.OUTCOME,
        "RESEARCH": ScientificEntityType.EXPERIMENT,
        "DISCOVERY": ScientificEntityType.KNOWLEDGE,
    }
    return mapping.get(stage, ScientificEntityType.DECISION)


# ── ExecutionOutcome adapter ───────────────────────────────────────────────────


def from_execution_outcome(outcome: Any, lineage_id: str) -> ScientificIdentity:
    """Adapt an ExecutionRuntime ExecutionOutcome to ScientificIdentity."""
    return ScientificIdentity(
        entity_type=ScientificEntityType.OUTCOME,
        entity_id=str(outcome.outcome_id),
        lineage_id=lineage_id,
        producer="data-core/execution_runtime",
        produced_at=_now_iso(),
        metadata={
            "session_id": str(getattr(outcome, "session_id", "")),
            "status": str(getattr(outcome, "status", "")),
        },
    )


# ── Generic event adapter ─────────────────────────────────────────────────────


def from_event(
    entity_type: ScientificEntityType,
    entity_id: str,
    lineage_id: str,
    producer: str,
    produced_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ScientificIdentity:
    """Generic adapter for any event-sourced entity."""
    return ScientificIdentity(
        entity_type=entity_type,
        entity_id=entity_id,
        lineage_id=lineage_id,
        producer=producer,
        produced_at=produced_at or _now_iso(),
        metadata=metadata or {},
    )


# ── BusinessOS claim adapter ───────────────────────────────────────────────────


def from_business_os_claim(claim_id: str, capability_id: str, lineage_id: str) -> ScientificIdentity:
    """Adapt a BusinessOS ScientificClaimDto to ScientificIdentity."""
    return ScientificIdentity(
        entity_type=ScientificEntityType.CLAIM,
        entity_id=claim_id,
        lineage_id=lineage_id,
        producer=f"business-os/foundation/{capability_id}",
        produced_at=_now_iso(),
        metadata={"capability_id": capability_id},
    )
