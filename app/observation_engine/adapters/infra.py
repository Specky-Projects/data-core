"""Infra (VPS) adapter — real collector.

Reuses the existing watchdog_runs table (the same data
app/watchdog/api.py already surfaces) for the infrastructure-wide health
signal, plus stdlib-only local disk usage (no new dependency — psutil is not
installed and is not added). CPU/RAM at VPS-process level remain PENDING per
COLLECTOR_SPECIFICATION.md until the Observer Framework wires a metrics
source (e.g. Prometheus scrape) — this collector never fabricates them.
"""
from __future__ import annotations

import shutil
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

_WATCHDOG_HEALTH = {
    "ok": ObservationHealth.HEALTHY,
    "healthy": ObservationHealth.HEALTHY,
    "warning": ObservationHealth.DEGRADED,
    "degraded": ObservationHealth.DEGRADED,
    "critical": ObservationHealth.CRITICAL,
}
_WATCHDOG_SEVERITY = {
    "ok": ObservationSeverity.INFO,
    "healthy": ObservationSeverity.INFO,
    "warning": ObservationSeverity.WARNING,
    "degraded": ObservationSeverity.WARNING,
    "critical": ObservationSeverity.CRITICAL,
}


class InfraAdapter:
    adapter_name = "infra"
    project = "poupi-infra"
    domain = "GENERIC"

    def collect(self) -> list[ObservationRecord]:
        ts = datetime.utcnow()
        metrics: dict[str, float] = {}
        evidence: list[str] = []
        health = ObservationHealth.UNKNOWN
        severity = ObservationSeverity.INFO

        try:
            usage = shutil.disk_usage(".")
            metrics["disk_used_pct"] = round(usage.used / usage.total * 100.0, 2)
            metrics["disk_free_gb"] = round(usage.free / (1024**3), 2)
        except OSError as exc:
            evidence.append(f"disk_usage error:{exc}")

        try:
            with SessionLocal() as db:
                row = db.execute(
                    text(
                        "SELECT overall_status, run_at, alert_codes FROM watchdog_runs "
                        "ORDER BY run_at DESC LIMIT 1"
                    )
                ).first()
            if row is not None:
                overall_status, run_at, alert_codes = row
                status_key = str(overall_status).lower()
                health = _WATCHDOG_HEALTH.get(status_key, ObservationHealth.UNKNOWN)
                severity = _WATCHDOG_SEVERITY.get(status_key, ObservationSeverity.WARNING)
                age_hours = (ts - run_at.replace(tzinfo=None)).total_seconds() / 3600.0
                metrics["watchdog_last_status_ok"] = 1.0 if status_key in ("ok", "healthy") else 0.0
                metrics["watchdog_last_run_age_hours"] = round(age_hours, 2)
                metrics["watchdog_alert_count"] = float(len(alert_codes or []))
                evidence.extend(f"alert_code:{c}" for c in (alert_codes or [])[:10])
                if age_hours > 24:
                    evidence.append(f"watchdog data is stale ({age_hours:.1f}h old) — not a live signal")
            else:
                evidence.append("no watchdog_runs rows found")
        except Exception as exc:  # noqa: BLE001 — collector must never crash the snapshot
            evidence.append(f"error:{type(exc).__name__}:{exc}")
            health = ObservationHealth.UNKNOWN
            severity = ObservationSeverity.ERROR

        return [
            ObservationRecord(
                observation_id=stable_hash({"source": "infra-vps", "ts": ts.isoformat()}),
                scientific_id=stable_hash({"producer": self.adapter_name, "ts": ts.isoformat()}),
                lineage_id=str(uuid4()),
                project=self.project,
                domain=self.domain,
                source="vps",
                severity=severity,
                health=health,
                evidence=list(evidence),
                metrics=metrics,
                timestamp=ts,
            )
        ]

    def health(self) -> dict:
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1 FROM watchdog_runs LIMIT 1"))
            return {"status": "HEALTHY", "adapter": self.adapter_name}
        except Exception as exc:  # noqa: BLE001
            return {"status": "UNKNOWN", "adapter": self.adapter_name, "error": str(exc)}
