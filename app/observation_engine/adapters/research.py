"""Research Engine adapter — real, self-observing (no production access).

Reports the local Research Engine's registered capability count and cache
state. It does not read Research Lab experiment results from production —
those remain PENDING the Observer Framework per COLLECTOR_SPECIFICATION.md.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.observation_engine.contracts import (
    ObservationHealth,
    ObservationRecord,
    ObservationSeverity,
)
from app.research_engine.engine import ResearchEngine
from app.scientific_identity.contract import stable_hash


class ResearchAdapter:
    adapter_name = "research"
    project = "business-os"
    domain = "GENERIC"

    def __init__(self) -> None:
        self._engine = ResearchEngine()

    def collect(self) -> list[ObservationRecord]:
        ts = datetime.utcnow()
        capability_count = len(self._engine._caps_impl)  # noqa: SLF001 — read-only introspection
        return [
            ObservationRecord(
                observation_id=stable_hash({"source": "research", "ts": ts.isoformat()}),
                scientific_id=stable_hash({"producer": self.adapter_name, "ts": ts.isoformat()}),
                lineage_id=str(uuid4()),
                project=self.project,
                domain=self.domain,
                source="research-engine",
                severity=ObservationSeverity.INFO,
                health=ObservationHealth.HEALTHY if capability_count > 0 else ObservationHealth.UNKNOWN,
                evidence=[],
                metrics={"capabilities_count": float(capability_count)},
                timestamp=ts,
            )
        ]

    def health(self) -> dict:
        return {"status": "HEALTHY", "adapter": self.adapter_name}
