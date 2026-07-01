"""Universal Platform adapter — real, self-observing (no production access).

Unlike the other adapters in this package, this one is NOT a synthetic stub:
it reports the actual local state of the Universal Platform process singleton
(see app.universal_platform.bootstrap), which requires no database, cache,
container runtime or VPS access — it is entirely in-process.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.observation_engine.contracts import (
    ObservationHealth,
    ObservationRecord,
    ObservationSeverity,
)
from app.scientific_identity.contract import stable_hash
from app.universal_platform.bootstrap import platform_status


class UniversalPlatformAdapter:
    adapter_name = "universal_platform"
    project = "business-os"
    domain = "GENERIC"

    def collect(self) -> list[ObservationRecord]:
        ts = datetime.utcnow()
        status = platform_status()
        initialized = bool(status.get("initialized"))
        health = ObservationHealth.HEALTHY if initialized else ObservationHealth.UNKNOWN
        severity = ObservationSeverity.INFO if initialized else ObservationSeverity.WARNING
        capabilities = status.get("capabilities") or []
        return [
            ObservationRecord(
                observation_id=stable_hash({"source": "universal_platform", "ts": ts.isoformat()}),
                scientific_id=stable_hash({"producer": self.adapter_name, "ts": ts.isoformat()}),
                lineage_id=str(uuid4()),
                project=self.project,
                domain=self.domain,
                source="universal-platform",
                severity=severity,
                health=health,
                evidence=[f"capability:{c}" for c in capabilities],
                metrics={
                    "initialized": 1.0 if initialized else 0.0,
                    "capabilities_count": float(len(capabilities)),
                    "adapters_count": float(len(status.get("adapters") or {})),
                },
                timestamp=ts,
            )
        ]

    def health(self) -> dict:
        status = platform_status()
        return {
            "status": "HEALTHY" if status.get("initialized") else "UNKNOWN",
            "adapter": self.adapter_name,
            "detail": status,
        }
