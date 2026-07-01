"""Observer Framework production pipeline — WS1 (continuous snapshots) + WS2
(diagnosis pipeline), wired exclusively from already-certified components:

    ObservationEngine -> RuntimeSnapshotBuilder -> RuntimeSnapshotContract
        -> SnapshotDiagnosisEngine.diagnose()
        -> SnapshotDiagnosisEngine.compare(previous, current)
        -> SnapshotDiagnosisEngine.certify(validation)
        -> ObserverSnapshotRun (persisted, never overwritten)
        -> Telegram executive summary

No new engine, contract, or adapter is introduced here — this module only
orchestrates calls to modules that already exist and are already tested
(app.observation_engine, app.observer_framework.{builder,diagnosis,
snapshot_contract}), and reuses the existing TelegramNotifier.

A collector failure never aborts a cycle: ObservationEngine.collect_all()
already converts adapter exceptions into degraded records (see
app/observation_engine/engine.py), so this pipeline only needs to catch
failures in the persistence/notification steps around that call.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.observer_framework.builder import RuntimeSnapshotBuilder
from app.observer_framework.diagnosis import SnapshotDiagnosisEngine
from app.observer_framework.models import ObserverSnapshotRun
from app.observer_framework.scoring import operational_score
from app.observer_framework.snapshot_contract import RuntimeSnapshotContract
from app.observer_framework.telegram_summary import format_executive_summary
from app.watchdog.notifier import TelegramNotifier

logger = logging.getLogger(__name__)


def _previous_snapshot(db: Session) -> RuntimeSnapshotContract | None:
    row = (
        db.query(ObserverSnapshotRun)
        .order_by(desc(ObserverSnapshotRun.captured_at))
        .first()
    )
    if row is None:
        return None
    return RuntimeSnapshotContract.from_dict(row.snapshot_json)


def run_observer_cycle(db: Session, *, send_telegram: bool = True) -> ObserverSnapshotRun:
    """Run one full Observation -> Snapshot -> Diagnosis -> Certification cycle.

    Persists exactly one new ObserverSnapshotRun row (history is never
    overwritten) and, unless ``send_telegram=False`` (used by tests/manual
    dry runs), sends one executive-summary Telegram message.
    """
    started = time.monotonic()

    builder = RuntimeSnapshotBuilder()
    engine = SnapshotDiagnosisEngine()

    current = builder.build()
    previous = _previous_snapshot(db) or current  # first-ever run compares to itself

    diagnosis = engine.diagnose(current)
    validation = engine.compare(previous, current)
    certification = engine.certify(validation)
    score = operational_score(diagnosis)

    duration_ms = int((time.monotonic() - started) * 1000)

    telegram_sent = False
    error_message: str | None = None
    if send_telegram:
        try:
            summary = format_executive_summary(diagnosis, validation, certification, score)
            telegram_sent = TelegramNotifier().send_plain(summary)
        except Exception as exc:  # noqa: BLE001 — never abort persistence over a notify failure
            logger.exception("observer_framework: telegram summary failed")
            error_message = str(exc)

    run = ObserverSnapshotRun(
        snapshot_id=current.snapshot_id,
        integrity_hash=current.integrity_hash,
        runtime_version=current.runtime_version,
        build_revision=current.build_revision,
        overall_health=diagnosis.overall_health,
        overall_severity=diagnosis.overall_severity,
        operational_score=score,
        classification=certification.classification,
        incident_count=len(diagnosis.incidents),
        new_incident_count=len(validation.new_incidents),
        resolved_incident_count=len(validation.resolved_incidents),
        duration_ms=duration_ms,
        snapshot_json=current.to_dict(),
        diagnosis_json=diagnosis.as_dict(),
        validation_json=validation.as_dict(),
        certification_json=certification.as_dict(),
        telegram_sent=telegram_sent,
        error_message=error_message,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    logger.info(
        "observer_framework: cycle complete",
        extra={
            "snapshot_id": current.snapshot_id,
            "classification": certification.classification,
            "operational_score": score,
            "incident_count": len(diagnosis.incidents),
            "duration_ms": duration_ms,
            "telegram_sent": telegram_sent,
        },
    )
    return run


def run_summary_dict(run: ObserverSnapshotRun) -> dict[str, Any]:
    """JSON-safe, advisory-only summary of a persisted run (no raw snapshot)."""
    return {
        "id": run.id,
        "captured_at": run.captured_at.isoformat() if run.captured_at else None,
        "snapshot_id": run.snapshot_id,
        "runtime_version": run.runtime_version,
        "build_revision": run.build_revision,
        "overall_health": run.overall_health,
        "overall_severity": run.overall_severity,
        "operational_score": run.operational_score,
        "classification": run.classification,
        "incident_count": run.incident_count,
        "new_incident_count": run.new_incident_count,
        "resolved_incident_count": run.resolved_incident_count,
        "duration_ms": run.duration_ms,
        "telegram_sent": run.telegram_sent,
    }
