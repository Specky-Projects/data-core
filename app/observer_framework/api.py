"""Observer Framework — FastAPI router.

Read-only history endpoints plus one manual-trigger endpoint used to validate
a cycle in production before enabling the twice-daily scheduler job. Nothing
here alters Mirror, Committee, Executor, Kill Switch, or Universal Platform —
it only runs the existing, already-certified observation/diagnosis pipeline
and persists/reads its own history table.

Prefix: /observer
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.observer_framework.models import ObserverSnapshotRun
from app.observer_framework.pipeline import run_observer_cycle, run_summary_dict
from core.config import settings
from database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/observer", tags=["observer-framework"])


@router.get("/latest")
def latest(db: Session = Depends(get_db)) -> dict:
    row = (
        db.query(ObserverSnapshotRun)
        .order_by(desc(ObserverSnapshotRun.captured_at))
        .first()
    )
    if row is None:
        return {"status": "no_runs_yet"}
    return run_summary_dict(row)


@router.get("/history")
def history(limit: int = 20, db: Session = Depends(get_db)) -> dict:
    limit = max(1, min(limit, 200))
    rows = (
        db.query(ObserverSnapshotRun)
        .order_by(desc(ObserverSnapshotRun.captured_at))
        .limit(limit)
        .all()
    )
    return {"count": len(rows), "runs": [run_summary_dict(r) for r in rows]}


@router.post("/run")
def run_now(send_telegram: bool = True, db: Session = Depends(get_db)) -> dict:
    """Manually trigger one Observer cycle. Advisory-only: reads/collects and
    persists a history row; never touches Mirror/Committee/Executor/Kill Switch.
    """
    if not settings.observer_framework_enabled:
        return {"status": "disabled", "reason": "OBSERVER_FRAMEWORK_ENABLED=false"}
    run = run_observer_cycle(db, send_telegram=send_telegram)
    return run_summary_dict(run)
