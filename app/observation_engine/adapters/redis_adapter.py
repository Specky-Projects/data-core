"""Redis adapter — real collector.

Reuses cache.client.get_redis() — the exact same accessor app/main.py's
/health and /ready endpoints already use. Reports "disabled" honestly when
settings.cache_enabled is False rather than fabricating numbers.
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
from core.config import settings


class RedisAdapter:
    adapter_name = "redis"
    project = "poupi-infra"
    domain = "GENERIC"

    def collect(self) -> list[ObservationRecord]:
        ts = datetime.utcnow()
        from cache.client import get_redis

        if not settings.cache_enabled:
            metrics = {"enabled": 0.0}
            health = ObservationHealth.UNKNOWN
            severity = ObservationSeverity.INFO
            evidence = ["cache_enabled=False — Redis intentionally disabled by config"]
        else:
            try:
                client = get_redis()
                if client is None:
                    raise RuntimeError("get_redis() returned None despite cache_enabled=True")
                info = client.info()
                metrics = {
                    "enabled": 1.0,
                    "used_memory_mb": round(info.get("used_memory", 0) / 1048576.0, 2),
                    "connected_clients": float(info.get("connected_clients", 0)),
                    "reachable": 1.0,
                }
                health = ObservationHealth.HEALTHY
                severity = ObservationSeverity.INFO
                evidence = []
            except Exception as exc:  # noqa: BLE001 — collector must never crash the snapshot
                metrics = {"enabled": 1.0, "reachable": 0.0}
                health = ObservationHealth.UNKNOWN
                severity = ObservationSeverity.ERROR
                evidence = [f"error:{type(exc).__name__}:{exc}"]

        return [
            ObservationRecord(
                observation_id=stable_hash({"source": "redis", "ts": ts.isoformat()}),
                scientific_id=stable_hash({"producer": self.adapter_name, "ts": ts.isoformat()}),
                lineage_id=str(uuid4()),
                project=self.project,
                domain=self.domain,
                source="redis",
                severity=severity,
                health=health,
                evidence=evidence,
                metrics=metrics,
                timestamp=ts,
            )
        ]

    def health(self) -> dict:
        if not settings.cache_enabled:
            return {"status": "DISABLED", "adapter": self.adapter_name}
        return {"status": "HEALTHY", "adapter": self.adapter_name}
