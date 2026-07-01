"""Scheduler adapter — real collector.

Reuses the existing apscheduler_jobs job-store table and pipeline_runs /
pipeline_failures tables — no new table, no new connection path.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import text

from app.observation_engine.contracts import (
    ObservationHealth,
    ObservationRecord,
    ObservationSeverity,
)
from app.scientific_identity.contract import stable_hash
from database.session import SessionLocal


class SchedulerAdapter:
    adapter_name = "scheduler"
    project = "poupi-infra"
    domain = "GENERIC"

    def collect(self) -> list[ObservationRecord]:
        ts = datetime.utcnow()
        try:
            with SessionLocal() as db:
                jobs_registered = db.execute(text("SELECT count(*) FROM apscheduler_jobs")).scalar()
                since = ts - timedelta(hours=24)
                runs_24h = db.execute(
                    text("SELECT count(*) FROM pipeline_runs WHERE started_at >= :since"),
                    {"since": since},
                ).scalar()
                failures_24h = db.execute(
                    text("SELECT count(*) FROM pipeline_failures WHERE occurred_at >= :since"),
                    {"since": since},
                ).scalar()
            metrics = {
                "jobs_registered": float(jobs_registered or 0),
                "pipeline_runs_24h": float(runs_24h or 0),
                "pipeline_failures_24h": float(failures_24h or 0),
                "reachable": 1.0,
            }
            health = ObservationHealth.HEALTHY if (failures_24h or 0) == 0 else ObservationHealth.DEGRADED
            severity = ObservationSeverity.INFO if (failures_24h or 0) == 0 else ObservationSeverity.WARNING
            evidence: list[str] = []
        except Exception as exc:  # noqa: BLE001 — collector must never crash the snapshot
            metrics = {"reachable": 0.0}
            health = ObservationHealth.UNKNOWN
            severity = ObservationSeverity.ERROR
            evidence = [f"error:{type(exc).__name__}:{exc}"]

        return [
            ObservationRecord(
                observation_id=stable_hash({"source": "scheduler", "ts": ts.isoformat()}),
                scientific_id=stable_hash({"producer": self.adapter_name, "ts": ts.isoformat()}),
                lineage_id=str(uuid4()),
                project=self.project,
                domain=self.domain,
                source="apscheduler",
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
                db.execute(text("SELECT count(*) FROM apscheduler_jobs"))
            return {"status": "HEALTHY", "adapter": self.adapter_name}
        except Exception as exc:  # noqa: BLE001
            return {"status": "UNKNOWN", "adapter": self.adapter_name, "error": str(exc)}
