"""Poupi Baby supervised runtime consumer bindings."""
from __future__ import annotations

from typing import Any

from app.scientific_consumers.facts import from_baby_opportunity
from app.scientific_consumers.runtime import (
    ScientificConsumerRuntime,
    ScientificConsumerRuntimeRecord,
)


class PoupiBabyScientificConsumer:
    """Recommendation-only consumer of the Scientific Decision Pipeline."""

    ADVISORY_ONLY = True
    AUTONOMOUS_EXECUTION = False

    def __init__(self, runtime: ScientificConsumerRuntime | None = None) -> None:
        self.runtime = runtime or ScientificConsumerRuntime()

    def recommend(self, opportunity_record: dict[str, Any]) -> ScientificConsumerRuntimeRecord:
        facts = from_baby_opportunity(opportunity_record)
        return self.runtime.materialize(facts)
