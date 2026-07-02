"""Opportunity Emitter Pipeline.

The only orchestration this phase adds: it wires an existing
``UniversalPlatform`` adapter (Replay / Explainability / Learning Feed /
Runtime Snapshot coverage, via ``UniversalObservationRuntime``) together with
a domain-specific ``build_opportunity`` function (pure adaptation, no
recomputation) and the ``OpportunityRegistry`` (EvaluationBundle / RankingScore
/ BusinessSnapshot composition). No scientific logic is added here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.business_os.contracts import Opportunity
from app.business_os.opportunity_emitters.registry import (
    OpportunityRegistration,
    OpportunityRegistry,
)
from app.universal_platform.adapters.base import BaseAdapter
from app.universal_platform.runtime import UniversalObservationRecord

BuildOpportunity = Callable[..., Opportunity]


@dataclass(frozen=True)
class OpportunityEmission:
    """Everything produced for one raw record: the Opportunity plus its full
    Observer Framework coverage (observation) and Business OS registration."""

    opportunity: Opportunity
    observation: UniversalObservationRecord
    registration: OpportunityRegistration

    @property
    def lineage_id(self) -> str:
        return self.observation.lineage_id

    def as_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity.opportunity_id,
            "domain": self.opportunity.domain.value,
            "status": self.opportunity.status.value,
            "lineage_id": self.lineage_id,
            "coverage": self.observation.coverage.as_dict(),
            "audit": self.observation.audit.as_dict(),
            "evaluation_ref": self.registration.evaluation.bundle_id,
            "ranking_ref": self.registration.ranking.ranking_id,
            "snapshot_ref": self.registration.snapshot.snapshot_id,
        }


def emit_opportunity(
    *,
    adapter: BaseAdapter,
    registry: OpportunityRegistry,
    raw: dict[str, Any],
    build_opportunity: BuildOpportunity,
    build_opportunity_kwargs: dict[str, Any] | None = None,
) -> OpportunityEmission:
    """Emit one Opportunity from one raw record produced by an existing domain.

    1. ``adapter.observe(raw)`` — reuses the Universal Observation Runtime to
       produce ObservationContract/ScientificIdentity/PipelineTrace/
       Explainability/ReplayManifest/ExecutionLedger/LearningFeed/
       CoverageMetrics/AuditSnapshot for this record (Observer Framework).
    2. ``build_opportunity(raw)`` — pure adaptation into the canonical
       ``Opportunity`` contract (no recomputation).
    3. ``registry.register(...)`` — links EvaluationBundle/RankingScore/
       BusinessSnapshot to the Opportunity and to the observation's
       lineage_id, so every emitted Opportunity is traceable back to its
       Replay/Explainability chain.
    """
    observation = adapter.observe(raw)
    opportunity = build_opportunity(raw, **(build_opportunity_kwargs or {}))
    registration = registry.register(
        opportunity,
        lineage_id=observation.lineage_id,
        evaluated_at=observation.event.occurred_at,
        computed_at=observation.event.occurred_at,
        captured_at=observation.event.occurred_at,
    )
    return OpportunityEmission(
        opportunity=opportunity,
        observation=observation,
        registration=registration,
    )
