"""Opportunity research capability."""
from __future__ import annotations

import uuid
from typing import Any

from app.research_engine.contracts import ResearchKind, ResearchResult


class OpportunityResearchCapability:
    name = "opportunity"

    def research(self, inputs: dict[str, Any]) -> ResearchResult:
        domain = inputs.get("domain", "GENERIC")
        return ResearchResult(
            result_id=str(uuid.uuid4()),
            kind=ResearchKind.OPPORTUNITY,
            findings=[{"domain": domain, "opportunity": "expand edge", "potential": "MEDIUM"}],
            summary=f"Opportunity research for {domain}",
            confidence=0.7,
            sources=["synthetic"],
            advisory_only=True,
        )
