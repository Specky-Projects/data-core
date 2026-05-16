"""Pipeline run recorder — persistence layer for PipelineRun / PipelineFailure.

This module provides ``PipelineRecorder``, a context manager that:

1. Inserts a ``PipelineRun`` row with status=running when the stage starts.
2. Updates the row (status, timing, counters) when the stage ends.
3. Inserts a ``PipelineFailure`` row on exception.
4. Records Prometheus metrics via ``api.metrics.measure_pipeline_stage``.
5. Injects ``pipeline_domain`` / ``pipeline_stage`` into structured logs.

Usage in scheduler/jobs.py::

    from app.pipeline.recorder import PipelineRecorder

    with PipelineRecorder(domain="crypto", stage="analytics", trigger="scheduler") as rec:
        processed = processor.run(limit=100)
        rec.items_processed = processed   # optional — update counter

The recorder is intentionally simple: it does NOT retry or suppress
exceptions.  Error handling is the caller's responsibility.
"""

from __future__ import annotations

import traceback
import uuid
from datetime import datetime, timezone
from types import TracebackType
from typing import Optional, Type

from api.metrics import (
    measure_pipeline_stage,
    pipeline_items_processed_total,
    pipeline_items_error_total,
)
from logs.config import clear_pipeline_context, set_pipeline_context


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PipelineRecorder:
    """Context manager that records a pipeline stage run and its metrics."""

    def __init__(
        self,
        *,
        domain: str,
        stage: str,
        source_name: str | None = None,
        trigger: str = "scheduler",
    ) -> None:
        self.domain = domain
        self.stage = stage
        self.source_name = source_name
        self.trigger = trigger

        # Counters the caller can update while inside the context
        self.items_input: int = 0
        self.items_processed: int = 0
        self.items_skipped: int = 0
        self.items_error: int = 0

        self._run_id: uuid.UUID | None = None
        self._started_at: datetime | None = None
        self._ctx_manager = None  # measure_pipeline_stage context

    # ── Context protocol ──────────────────────────────────────────────────────

    def __enter__(self) -> "PipelineRecorder":
        self._started_at = _now()
        set_pipeline_context(domain=self.domain, stage=self.stage)
        self._run_id = self._insert_run()
        self._ctx_manager = measure_pipeline_stage(self.domain, self.stage)
        self._ctx_manager.__enter__()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        # Exit the Prometheus context manager first (records duration/status)
        suppress = False
        if self._ctx_manager is not None:
            try:
                self._ctx_manager.__exit__(exc_type, exc_val, exc_tb)
            except Exception:
                pass

        finished_at = _now()
        duration = (finished_at - self._started_at).total_seconds() if self._started_at else None

        if exc_type is not None:
            status = "error"
            self._insert_failure(
                error_type=exc_type.__name__,
                error_message=str(exc_val),
                tb="".join(traceback.format_tb(exc_tb)) if exc_tb else None,
                is_terminal=True,
            )
            pipeline_items_error_total.labels(
                domain=self.domain, stage=self.stage
            ).inc()
        elif self.items_error > 0:
            status = "partial"
        else:
            status = "success"

        # Update Prometheus item counters
        if self.items_processed > 0:
            pipeline_items_processed_total.labels(
                domain=self.domain, stage=self.stage
            ).inc(self.items_processed)

        self._update_run(status=status, finished_at=finished_at, duration=duration)
        clear_pipeline_context()
        return suppress  # do not suppress exceptions

    # ── DB helpers ────────────────────────────────────────────────────────────

    def _insert_run(self) -> uuid.UUID | None:
        try:
            from app.pipeline.models import PipelineRun
            from database.session import SessionLocal

            run_id = uuid.uuid4()
            db = SessionLocal()
            try:
                run = PipelineRun(
                    id=run_id,
                    domain=self.domain,
                    stage=self.stage,
                    source_name=self.source_name,
                    started_at=self._started_at,
                    status="running",
                    trigger=self.trigger,
                )
                db.add(run)
                db.commit()
            finally:
                db.close()
            return run_id
        except Exception:
            # Never let observability break the pipeline
            return None

    def _update_run(
        self, *, status: str, finished_at: datetime, duration: float | None
    ) -> None:
        if self._run_id is None:
            return
        try:
            from app.pipeline.models import PipelineRun
            from database.session import SessionLocal

            db = SessionLocal()
            try:
                run = db.get(PipelineRun, self._run_id)
                if run:
                    run.status = status
                    run.finished_at = finished_at
                    run.duration_seconds = duration
                    run.items_input = self.items_input
                    run.items_processed = self.items_processed
                    run.items_skipped = self.items_skipped
                    run.items_error = self.items_error
                    db.commit()
            finally:
                db.close()
        except Exception:
            pass

    def _insert_failure(
        self,
        *,
        error_type: str,
        error_message: str,
        tb: str | None,
        is_terminal: bool = False,
        item_id: str | None = None,
        item_context: dict | None = None,
        retry_count: int = 0,
    ) -> None:
        if self._run_id is None:
            return
        try:
            from app.pipeline.models import PipelineFailure
            from database.session import SessionLocal

            db = SessionLocal()
            try:
                failure = PipelineFailure(
                    run_id=self._run_id,
                    domain=self.domain,
                    stage=self.stage,
                    error_type=error_type,
                    error_message=error_message[:4096],
                    traceback=tb,
                    item_id=item_id,
                    item_context=item_context,
                    retry_count=retry_count,
                    is_terminal=is_terminal,
                )
                db.add(failure)
                db.commit()
            finally:
                db.close()
        except Exception:
            pass
