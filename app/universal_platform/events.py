"""UniversalEvent — the single generic event every Phase 2 adapter emits.

An adapter never invents a new contract: it normalises a project event into a
``UniversalEvent`` and projects it onto the *existing* internal ``DecisionFacts``
value object, which the Phase 1 Scientific Runtime already knows how to
materialise into the full scientific chain.

Nothing here decides anything. A UniversalEvent records a fact that *already
happened* in a source system (an opportunity was discovered, a container
restarted, a click converted). Construction is pure and deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.scientific_consumers.facts import (
    DecisionFacts,
    EvidenceFact,
    OutcomeFact,
    _clamp01,
    _evidence_from,
    _f,
    _outcome_from,
)
from app.scientific_identity.contract import stable_hash


class Severity(str, Enum):
    """Ordered severity taxonomy shared by observations and alerts."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self]


_SEVERITY_RANK = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


def coerce_severity(value: Any) -> Severity:
    if isinstance(value, Severity):
        return value
    try:
        return Severity(str(value).upper())
    except ValueError:
        return Severity.INFO


@dataclass(frozen=True)
class UniversalEvent:
    """A project fact, normalised for the universal adapter layer."""

    project: str              # "mirror" | "poupi-baby" | "infrastructure" | ...
    domain: str               # DecisionFacts.domain (free string)
    event_type: str           # "opportunity.discovered" | "redis.restart" | ...
    entity_id: str            # candidate_id — symbol / product / service / campaign
    occurred_at: str
    confidence: float = 1.0
    severity: Severity = Severity.INFO
    evidence: tuple[EvidenceFact, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    outcome: OutcomeFact | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def event_id(self) -> str:
        return stable_hash(
            {
                "project": self.project,
                "domain": self.domain,
                "event_type": self.event_type,
                "entity_id": self.entity_id,
                "occurred_at": self.occurred_at,
            }
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.project.strip():
            errors.append("project must not be empty")
        if not self.domain.strip():
            errors.append("domain must not be empty")
        if not self.event_type.strip():
            errors.append("event_type must not be empty")
        if not self.entity_id.strip():
            errors.append("entity_id must not be empty")
        if not self.occurred_at.strip():
            errors.append("occurred_at must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            errors.append("confidence must be within [0, 1]")
        return errors

    @classmethod
    def create(
        cls,
        *,
        project: str,
        domain: str,
        event_type: str,
        entity_id: str,
        occurred_at: str,
        confidence: float = 1.0,
        severity: Any = Severity.INFO,
        evidence: Any = (),
        metrics: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        outcome: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> UniversalEvent:
        """Factory that tolerates raw dict inputs from source systems."""
        ev: tuple[EvidenceFact, ...]
        if evidence and isinstance(evidence[0], EvidenceFact):  # type: ignore[index]
            ev = tuple(evidence)
        else:
            ev = _evidence_from(evidence)
        oc = outcome if isinstance(outcome, OutcomeFact) or outcome is None else _outcome_from(outcome)
        return cls(
            project=project,
            domain=domain,
            event_type=event_type,
            entity_id=entity_id,
            occurred_at=occurred_at,
            confidence=_clamp01(_f(confidence, 1.0)),
            severity=coerce_severity(severity),
            evidence=ev,
            metrics=dict(metrics or {}),
            payload=dict(payload or {}),
            outcome=oc,
            metadata=dict(metadata or {}),
        )


def to_decision_facts(event: UniversalEvent) -> DecisionFacts:
    """Project a UniversalEvent onto the existing internal DecisionFacts.

    Neutral, non-deciding mapping: an observation is not a verdict. Bayesian
    fields are set to a neutral prior and the recorded confidence as posterior;
    the committee block abstains. The Phase 1 runtime records these verbatim.
    """
    conf = _clamp01(event.confidence)
    ev_weight = _clamp01(len(event.evidence) / 5.0) if event.evidence else 0.0
    return DecisionFacts(
        consumer=event.project,
        domain=event.domain,
        decision_id=event.event_id,
        candidate_id=event.entity_id,
        strategy=event.event_type,
        regime=event.severity.value,
        decided_at=event.occurred_at,
        verdict="OBSERVED",
        action="OBSERVE",
        confidence=conf,
        prior=0.5,
        likelihood=0.5,
        posterior=conf,
        evidence_weight=ev_weight,
        committee_verdict="ABSTAIN",
        committee_confidence=0.0,
        committee_quorum_met=False,
        committee_members=(),
        committee_dissenting=0,
        evidence=event.evidence,
        risk=None,
        expected_edge=None,
        simulation_only=True,
        requires_human_review=True,
        outcome=event.outcome,
        raw={
            "project": event.project,
            "event_type": event.event_type,
            "severity": event.severity.value,
            "metrics": event.metrics,
            "payload": event.payload,
            "metadata": event.metadata,
        },
    )
