"""Opportunity Emitters — Business OS 6.0 Phase 1.

Converts the already-existing outputs of Research Lab and Poupi Baby into the
canonical ``business_os.contracts.Opportunity``. No statistic is recomputed
and no new engine is created: these modules only adapt an existing raw dict
into the canonical contract and register it via the existing composition
contracts (``EvaluationBundle``, ``RankingScore``, ``BusinessSnapshot``).
"""
from __future__ import annotations

from app.business_os.opportunity_emitters.pipeline import (
    OpportunityEmission,
    emit_opportunity,
)
from app.business_os.opportunity_emitters.poupi_baby import (
    build_opportunity_from_poupi_baby,
)
from app.business_os.opportunity_emitters.registry import (
    OpportunityRegistration,
    OpportunityRegistry,
)
from app.business_os.opportunity_emitters.research_lab import (
    build_opportunity_from_research,
)

__all__ = [
    "OpportunityEmission",
    "OpportunityRegistration",
    "OpportunityRegistry",
    "build_opportunity_from_poupi_baby",
    "build_opportunity_from_research",
    "emit_opportunity",
]
