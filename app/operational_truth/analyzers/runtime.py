"""RuntimeTruthAnalyzer — scheduler, worker, queue, restart-loop detection."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.operational_truth.dto import RuntimeTruth, classify_score
from app.runtime.scheduler_heartbeat import read_scheduler_heartbeat, heartbeat_age_seconds
from core.config import settings


def _worker_heartbeat_age() -> tuple[bool, float | None]:
    """Return (alive, age_seconds) for the worker process."""
    try:
        from app.runtime.heartbeat import read_worker_heartbeat
        hb = read_worker_heartbeat()
        if not hb:
            return False, None
        ts = hb.get("timestamp_epoch")
        if ts is None:
            return False, None
        now = datetime.now(timezone.utc).timestamp()
        age = now - float(ts)
        max_age = max(settings.worker_pipeline_interval_seconds * 2, 180)
        alive = hb.get("status") != "stopped" and age <= max_age
        return alive, age
    except Exception:
        return False, None


def _queue_backlog(db: Session) -> int:
    try:
        from app.raw.models import RawCollection
        return db.query(RawCollection).filter(
            RawCollection.processing_status == "normalization_pending"
        ).count()
    except Exception:
        return 0


def _queue_pressure(backlog: int) -> int:
    """Convert raw backlog count to a pressure score 0-100 (higher = worse)."""
    if backlog == 0:
        return 0
    if backlog <= 50:
        return 20
    if backlog <= 200:
        return 50
    if backlog <= 500:
        return 75
    return 100


def analyze_runtime(db: Session) -> RuntimeTruth:
    findings: list[str] = []
    now = datetime.now(timezone.utc)

    # ── Scheduler heartbeat ────────────────────────────────────────────────────
    hb = read_scheduler_heartbeat()
    hb_age = heartbeat_age_seconds()
    scheduler_alive = False
    scheduler_stale = True
    scheduler_consecutive_failures = 0
    restart_loop_detected = False

    if hb is not None:
        scheduler_consecutive_failures = hb.get("consecutive_failures", 0)
        if hb_age is not None:
            if hb_age <= 600:  # 10 min
                scheduler_alive = True
                scheduler_stale = False
            elif hb_age <= 1800:  # 30 min
                findings.append(f"scheduler_stale: heartbeat {hb_age:.0f}s old")
            else:
                findings.append(f"scheduler_dead: heartbeat {hb_age:.0f}s old")
        if scheduler_consecutive_failures >= 3:
            restart_loop_detected = True
            findings.append(f"scheduler_restart_loop: {scheduler_consecutive_failures} consecutive failures")
    else:
        findings.append("scheduler_heartbeat_missing")

    if not settings.scheduler_enabled:
        scheduler_alive = True  # not expected to run
        scheduler_stale = False

    # ── Worker heartbeat ───────────────────────────────────────────────────────
    worker_alive, worker_age = _worker_heartbeat_age()
    if not worker_alive:
        findings.append(f"worker_dead_or_stale: age={worker_age}")

    # ── Queue backlog ──────────────────────────────────────────────────────────
    backlog = _queue_backlog(db)
    pressure = _queue_pressure(backlog)
    if backlog > 500:
        findings.append(f"queue_explosion: {backlog} pending items")
    elif backlog > 200:
        findings.append(f"queue_pressure_high: {backlog} pending items")
    elif backlog > 50:
        findings.append(f"queue_pressure_moderate: {backlog} pending items")

    # ── Fail-open risk ─────────────────────────────────────────────────────────
    # Fail-open means: scheduler running but jobs silently failing
    fail_open_risk = (
        scheduler_alive
        and scheduler_consecutive_failures >= 2
        and backlog > 100
    )
    if fail_open_risk:
        findings.append("fail_open_risk: scheduler alive but jobs silently failing into backlog")

    # ── Score ──────────────────────────────────────────────────────────────────
    score = 100
    if not scheduler_alive and settings.scheduler_enabled:
        score -= 35
    if scheduler_stale:
        score -= 15
    if restart_loop_detected:
        score -= 20
    if not worker_alive:
        score -= 20
    if pressure >= 75:
        score -= 25
    elif pressure >= 50:
        score -= 15
    elif pressure >= 20:
        score -= 5
    if fail_open_risk:
        score -= 10

    score = max(0, score)
    return RuntimeTruth(
        score=score,
        status=classify_score(score),
        scheduler_alive=scheduler_alive,
        scheduler_heartbeat_age_seconds=hb_age,
        scheduler_consecutive_failures=scheduler_consecutive_failures,
        scheduler_stale=scheduler_stale,
        worker_alive=worker_alive,
        worker_heartbeat_age_seconds=worker_age,
        queue_backlog=backlog,
        queue_pressure_score=pressure,
        restart_loop_detected=restart_loop_detected,
        fail_open_risk=fail_open_risk,
        findings=findings,
        evaluated_at=now,
    )
