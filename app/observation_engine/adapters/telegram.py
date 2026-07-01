"""Telegram adapter — real collector.

Reuses the existing telegram_delivery_audit / telegram_publication_events
tables — the same ledger app/watchdog and app/alerts already write to. No new
bot token, no new API call.
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


class TelegramAdapter:
    adapter_name = "telegram"
    project = "poupi-notifications"
    domain = "GENERIC"

    def collect(self) -> list[ObservationRecord]:
        ts = datetime.utcnow()
        try:
            since = ts - timedelta(hours=24)
            with SessionLocal() as db:
                sent_24h = db.execute(
                    text(
                        "SELECT count(*) FROM telegram_delivery_audit "
                        "WHERE created_at >= :since AND status = 'sent'"
                    ),
                    {"since": since},
                ).scalar()
                errors_24h = db.execute(
                    text(
                        "SELECT count(*) FROM telegram_delivery_audit "
                        "WHERE created_at >= :since AND status != 'sent'"
                    ),
                    {"since": since},
                ).scalar()
                total_audited = db.execute(text("SELECT count(*) FROM telegram_delivery_audit")).scalar()
            metrics = {
                "messages_sent_24h": float(sent_24h or 0),
                "errors_24h": float(errors_24h or 0),
                "total_audited": float(total_audited or 0),
                "reachable": 1.0,
            }
            health = ObservationHealth.HEALTHY if (errors_24h or 0) == 0 else ObservationHealth.DEGRADED
            severity = ObservationSeverity.INFO if (errors_24h or 0) == 0 else ObservationSeverity.WARNING
            evidence: list[str] = []
        except Exception as exc:  # noqa: BLE001 — collector must never crash the snapshot
            metrics = {"reachable": 0.0}
            health = ObservationHealth.UNKNOWN
            severity = ObservationSeverity.ERROR
            evidence = [f"error:{type(exc).__name__}:{exc}"]

        return [
            ObservationRecord(
                observation_id=stable_hash({"source": "telegram", "ts": ts.isoformat()}),
                scientific_id=stable_hash({"producer": self.adapter_name, "ts": ts.isoformat()}),
                lineage_id=str(uuid4()),
                project=self.project,
                domain=self.domain,
                source="telegram-bot",
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
                db.execute(text("SELECT 1 FROM telegram_delivery_audit LIMIT 1"))
            return {"status": "HEALTHY", "adapter": self.adapter_name}
        except Exception as exc:  # noqa: BLE001
            return {"status": "UNKNOWN", "adapter": self.adapter_name, "error": str(exc)}
