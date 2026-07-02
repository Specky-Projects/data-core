"""Opportunity Registry — composition-only bookkeeping for emitted Opportunities.

Every method here only *wires references* between contracts that already
exist in ``business_os.contracts``. It never recomputes confidence,
expected_value, or any ranking/evaluation logic — ``RankingScore`` and
``EvaluationBundle`` are built strictly from values the Opportunity (or its
Universal Platform observation) already carries.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.business_os.contracts import (
    BusinessSnapshot,
    EvaluationBundle,
    Opportunity,
    RankingScore,
)


@dataclass(frozen=True)
class OpportunityRegistration:
    """The full set of canonical contracts linked to one emitted Opportunity."""

    opportunity: Opportunity
    evaluation: EvaluationBundle
    ranking: RankingScore
    snapshot: BusinessSnapshot


class OpportunityRegistry:
    """In-process registry of Opportunities and their linked composition contracts.

    Not a new engine: this is the same composition-by-reference pattern the
    ``EvaluationBundle``/``RankingScore``/``BusinessSnapshot`` docstrings in
    ``business_os/contracts.py`` already describe. Persistence (a table
    backing this registry) is explicitly out of scope for this phase.
    """

    def __init__(self) -> None:
        self._registrations: dict[str, OpportunityRegistration] = {}

    def register(
        self,
        opportunity: Opportunity,
        *,
        lineage_id: str,
        evaluated_at: str,
        computed_at: str,
        captured_at: str,
        confidence_ref: str | None = None,
        explainability_ref: str | None = None,
        replay_ref: str | None = None,
    ) -> OpportunityRegistration:
        errors = opportunity.validate()
        if errors:
            raise ValueError(f"invalid Opportunity: {'; '.join(errors)}")

        evaluation = EvaluationBundle(
            bundle_id=f"eval:{opportunity.opportunity_id}",
            domain=opportunity.domain,
            evidence_refs=opportunity.evidence_refs,
            context_ref=None,
            statistics_ref=None,
            confidence_ref=confidence_ref or lineage_id,
            explainability_ref=explainability_ref or lineage_id,
            replay_ref=replay_ref or lineage_id,
            evaluated_at=evaluated_at,
            metadata={"opportunity_ref": opportunity.opportunity_id},
        )
        eval_errors = evaluation.validate()
        if eval_errors:
            raise ValueError(f"invalid EvaluationBundle: {'; '.join(eval_errors)}")

        ranking = RankingScore(
            ranking_id=f"rank:{opportunity.opportunity_id}",
            opportunity_ref=opportunity.opportunity_id,
            confidence_ref=confidence_ref or lineage_id,
            priority=opportunity.confidence,
            impact=opportunity.confidence,
            roi=opportunity.expected_value,
            urgency=None,
            computed_at=computed_at,
            rationale="passthrough from Opportunity.confidence/expected_value — no recomputation",
            metadata={"domain": opportunity.domain.value},
        )
        ranking_errors = ranking.validate()
        if ranking_errors:
            raise ValueError(f"invalid RankingScore: {'; '.join(ranking_errors)}")

        snapshot = BusinessSnapshot(
            snapshot_id=f"snap:{opportunity.opportunity_id}:{captured_at}",
            domain=opportunity.domain,
            captured_at=captured_at,
            opportunity_ref=opportunity.opportunity_id,
            evaluation_ref=evaluation.bundle_id,
            ranking_ref=ranking.ranking_id,
            execution_plan_ref=None,
            execution_ref=None,
            outcome_ref=None,
            learning_ref=lineage_id,
            knowledge_refs=(),
            metadata={"lineage_id": lineage_id},
        )
        snapshot_errors = snapshot.validate()
        if snapshot_errors:
            raise ValueError(f"invalid BusinessSnapshot: {'; '.join(snapshot_errors)}")

        registration = OpportunityRegistration(
            opportunity=opportunity,
            evaluation=evaluation,
            ranking=ranking,
            snapshot=snapshot,
        )
        self._registrations[opportunity.opportunity_id] = registration
        return registration

    def get(self, opportunity_id: str) -> OpportunityRegistration | None:
        return self._registrations.get(opportunity_id)

    def all(self) -> tuple[OpportunityRegistration, ...]:
        return tuple(self._registrations.values())

    def count(self) -> int:
        return len(self._registrations)
