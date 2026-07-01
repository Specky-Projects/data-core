"""Postgres adapter — real collector.

Reuses the exact same SessionLocal() the app's own /health and /ready
endpoints use (app/main.py). No new connection path, no new credentials.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import text

from app.observation_engine.contracts import (
    ObservationHealth,
    ObservationRecord,
    ObservationSeverity,
)
from app.scientific_identity.contract import stable_hash
from database.session import SessionLocal


class PostgresAdapter:
    adapter_name = "postgres"
    project = "poupi-infra"
    domain = "GENERIC"

    def collect(self) -> list[ObservationRecord]:
        ts = datetime.utcnow()
        try:
            with SessionLocal() as db:
                active_connections = db.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
                ).scalar()
                db_size_mb = db.execute(
                    text("SELECT pg_database_size(current_database()) / 1048576.0")
                ).scalar()
            metrics = {
                "active_connections": float(active_connections or 0),
                "db_size_mb": round(float(db_size_mb or 0.0), 2),
                "reachable": 1.0,
            }
            health = ObservationHealth.HEALTHY
            severity = ObservationSeverity.INFO
            evidence: list[str] = []
        except Exception as exc:  # noqa: BLE001 — collector must never crash the snapshot
            metrics = {"reachable": 0.0}
            health = ObservationHealth.UNKNOWN
            severity = ObservationSeverity.ERROR
            evidence = [f"error:{type(exc).__name__}:{exc}"]

        return [
            ObservationRecord(
                observation_id=stable_hash({"source": "postgres", "ts": ts.isoformat()}),
                scientific_id=stable_hash({"producer": self.adapter_name, "ts": ts.isoformat()}),
                lineage_id=str(uuid4()),
                project=self.project,
                domain=self.domain,
                source="postgresql",
                severity=severity,
                health=health,
                evidence=evidence,
                metrics=metrics,
                timestamp=ts,
            )
        ]

    def health(self) -> dict:
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
            return {"status": "HEALTHY", "adapter": self.adapter_name}
        except Exception as exc:  # noqa: BLE001
            return {"status": "UNKNOWN", "adapter": self.adapter_name, "error": str(exc)}
