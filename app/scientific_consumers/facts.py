"""DecisionFacts — internal, read-only normalisation of a consumer decision.

This is NOT a new contract. It is a plain internal value object that captures
the facts a consumer (Mirror, Poupi Baby) has *already* produced, so the
binding modules can project those facts onto the canonical contracts uniformly.

Nothing here decides anything: a Mirror verdict / Baby evaluation is taken as
given and only re-expressed. Construction is pure and deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.scientific_identity.builder import ScientificIdentityBuilder


@dataclass(frozen=True)
class EvidenceFact:
    evidence_id: str
    source_type: str
    source_name: str
    evidence_level: str
    quality_score: float | None = None
    contribution_weight: float | None = None
    used: bool = True


@dataclass(frozen=True)
class CommitteeMemberFact:
    member_id: str
    vote: str
    weight: float
    rationale: str | None = None


@dataclass(frozen=True)
class OutcomeFact:
    kind: str  # SUCCESS | FAILURE | PARTIAL | INCONCLUSIVE
    realized_value: float | None
    expected_value: float | None
    recorded_at: str


@dataclass(frozen=True)
class DecisionFacts:
    """Everything an observer needs about a decision that already happened."""

    # identity / provenance
    consumer: str            # "mirror" | "poupi-baby"
    domain: str              # "CRYPTO" | "POUPI_BABY"
    decision_id: str
    candidate_id: str        # symbol / product / opportunity ref
    strategy: str | None
    regime: str | None
    decided_at: str

    # decision result (recorded verbatim — never altered)
    verdict: str             # APPROVE | REJECT | DEFER ...
    action: str              # ENTER_LONG | NO_ACTION | RECOMMEND ...
    confidence: float
    prior: float
    likelihood: float
    posterior: float
    evidence_weight: float

    committee_verdict: str
    committee_confidence: float
    committee_quorum_met: bool
    committee_members: tuple[CommitteeMemberFact, ...]
    committee_dissenting: int

    evidence: tuple[EvidenceFact, ...]
    risk: float | None = None
    expected_edge: float | None = None
    simulation_only: bool = True
    requires_human_review: bool = False
    outcome: OutcomeFact | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    # ---- deterministic lineage -------------------------------------------
    @property
    def lineage_id(self) -> str:
        """Stable lineage for the whole decision lifecycle."""
        return ScientificIdentityBuilder.derive_lineage_id(
            self.consumer, self.domain, self.decision_id
        )

    def producer(self) -> str:
        return f"{self.consumer}-scientific-consumer"


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _evidence_from(rows: Any) -> tuple[EvidenceFact, ...]:
    out: list[EvidenceFact] = []
    for i, r in enumerate(rows or []):
        out.append(
            EvidenceFact(
                evidence_id=str(r.get("evidence_id") or f"ev-{i}"),
                source_type=str(r.get("source_type") or "GENERIC"),
                source_name=str(r.get("source_name") or "unknown"),
                evidence_level=str(r.get("evidence_level") or "RAW"),
                quality_score=(None if r.get("quality_score") is None
                               else _clamp01(_f(r.get("quality_score")))),
                contribution_weight=(None if r.get("contribution_weight") is None
                                     else _clamp01(_f(r.get("contribution_weight")))),
                used=bool(r.get("used", True)),
            )
        )
    return tuple(out)


def _committee_from(block: Any) -> tuple[str, float, bool, tuple[CommitteeMemberFact, ...], int]:
    block = block or {}
    members = tuple(
        CommitteeMemberFact(
            member_id=str(m.get("member_id") or f"m-{i}"),
            vote=str(m.get("vote") or "ABSTAIN"),
            weight=_f(m.get("weight"), 1.0),
            rationale=m.get("rationale"),
        )
        for i, m in enumerate(block.get("members") or [])
    )
    return (
        str(block.get("verdict") or "ABSTAIN"),
        _clamp01(_f(block.get("confidence"))),
        bool(block.get("quorum_met", bool(members))),
        members,
        int(block.get("dissenting") or 0),
    )


def _outcome_from(block: Any) -> OutcomeFact | None:
    if not block:
        return None
    return OutcomeFact(
        kind=str(block.get("kind") or "INCONCLUSIVE"),
        realized_value=(None if block.get("realized_value") is None
                        else _f(block.get("realized_value"))),
        expected_value=(None if block.get("expected_value") is None
                        else _f(block.get("expected_value"))),
        recorded_at=str(block.get("recorded_at") or ""),
    )


def from_mirror_decision(record: dict[str, Any]) -> DecisionFacts:
    """Normalise a Mirror decision record (read-only).

    Mirror already decided. We only re-express its verdict/action/posterior.
    """
    cv, cc, cq, cm, cd = _committee_from(record.get("committee"))
    return DecisionFacts(
        consumer="mirror",
        domain="CRYPTO",
        decision_id=str(record["decision_id"]),
        candidate_id=str(record.get("symbol") or record.get("candidate_id") or "UNKNOWN"),
        strategy=record.get("strategy"),
        regime=record.get("regime"),
        decided_at=str(record.get("decided_at") or ""),
        verdict=str(record.get("verdict") or cv),
        action=str(record.get("action") or "NO_ACTION"),
        confidence=_clamp01(_f(record.get("confidence", cc))),
        prior=_clamp01(_f(record.get("prior"))),
        likelihood=_clamp01(_f(record.get("likelihood"))),
        posterior=_clamp01(_f(record.get("posterior"))),
        evidence_weight=_clamp01(_f(record.get("evidence_weight"))),
        committee_verdict=cv,
        committee_confidence=cc,
        committee_quorum_met=cq,
        committee_members=cm,
        committee_dissenting=cd,
        evidence=_evidence_from(record.get("evidence")),
        risk=(None if record.get("risk") is None else _clamp01(_f(record.get("risk")))),
        expected_edge=(None if record.get("expected_edge") is None
                       else _f(record.get("expected_edge"))),
        simulation_only=bool(record.get("simulation_only", True)),
        requires_human_review=False,
        outcome=_outcome_from(record.get("outcome")),
        raw=dict(record),
    )


def from_baby_opportunity(record: dict[str, Any]) -> DecisionFacts:
    """Normalise a Poupi Baby opportunity into supervised-recommendation facts.

    Recommendation only — requires_human_review is always True and no action
    beyond RECOMMEND is ever emitted.
    """
    cv, cc, cq, cm, cd = _committee_from(record.get("committee"))
    return DecisionFacts(
        consumer="poupi-baby",
        domain="POUPI_BABY",
        decision_id=str(record["opportunity_id"]),
        candidate_id=str(record.get("product") or record.get("candidate_id") or "UNKNOWN"),
        strategy=record.get("category") or record.get("strategy"),
        regime=record.get("regime"),
        decided_at=str(record.get("discovered_at") or record.get("decided_at") or ""),
        verdict=str(record.get("verdict") or "RECOMMEND"),
        action="RECOMMEND",
        confidence=_clamp01(_f(record.get("confidence", cc))),
        prior=_clamp01(_f(record.get("prior"))),
        likelihood=_clamp01(_f(record.get("likelihood"))),
        posterior=_clamp01(_f(record.get("posterior", record.get("confidence")))),
        evidence_weight=_clamp01(_f(record.get("evidence_weight"))),
        committee_verdict=cv,
        committee_confidence=cc,
        committee_quorum_met=cq,
        committee_members=cm,
        committee_dissenting=cd,
        evidence=_evidence_from(record.get("evidence")),
        risk=(None if record.get("risk") is None else _clamp01(_f(record.get("risk")))),
        expected_edge=(None if record.get("expected_value") is None
                       else _f(record.get("expected_value"))),
        simulation_only=True,
        requires_human_review=True,
        outcome=_outcome_from(record.get("outcome")),
        raw=dict(record),
    )
