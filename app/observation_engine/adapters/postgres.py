"""Postgres adapter — synthetic stub."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.observation_engine.contracts import (
    ObservationHealth,
    ObservationRecord,
    ObservationSeverity,
)
from app.scientific_identity.contract import stable_hash


class PostgresAdapter:
    adapter_name = "postgres"
    project = "poupi-infra"
    domain = "GENERIC"

    def collect(self) -> list[ObservationRecord]:
        ts = datetime.utcnow()
        return [
            ObservationRecord(
                observation_id=stable_hash({"source": "postgres", "ts": ts.isoformat()}),
                scientific_id=stable_hash({"producer": self.adapter_name, "ts": ts.isoformat()}),
                lineage_id=str(uuid4()),
                project=self.project,
                domain=self.domain,
                source="postgresql",
                severity=ObservationSeverity.INFO,
                health=ObservationHealth.HEALTHY,
                evidence=[],
                metrics={"active_connections": 8, "db_size_mb": 312.4},
                timestamp=ts,
            )
        ]

    def health(self) -> dict:
        return {"status": "HEALTHY", "adapter": self.adapter_name}
