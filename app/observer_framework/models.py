"""SQLAlchemy model for Observer Framework operational history.

Follows the same shape as app.watchdog.models.WatchdogRun: one row per
pipeline execution, timestamp + JSONB blobs. Reuses the existing
RuntimeSnapshotContract / OperationalDiagnosis / ValidationResult / Certification
dataclasses (via their .to_dict()/.as_dict()) — this table only persists what
those already-certified components produce. No new engine, no new contract.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database.models import Base


class ObserverSnapshotRun(Base):
    """Records each execution of the Observer Framework snapshot+diagnosis cycle.

    One row = one RuntimeSnapshotContract + its OperationalDiagnosis + the
    ValidationResult/Certification produced by comparing it against the
    previous run. Snapshots are never overwritten — every run is a new row.
    """

    __tablename__ = "observer_snapshot_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    integrity_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    runtime_version: Mapped[str] = mapped_column(String(64), nullable=False)
    build_revision: Mapped[str | None] = mapped_column(String(64), nullable=True)

    overall_health: Mapped[str] = mapped_column(String(16), nullable=False)
    overall_severity: Mapped[str] = mapped_column(String(16), nullable=False)
    operational_score: Mapped[float] = mapped_column(Float, nullable=False)
    classification: Mapped[str] = mapped_column(
        String(24), nullable=False, comment="GO | GO_WITH_OBSERVATIONS | NO_GO"
    )

    incident_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_incident_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolved_incident_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Full JSON payloads — never overwritten, always auditable/replayable.
    snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    diagnosis_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    validation_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    certification_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    telegram_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ObserverSnapshotRun id={self.id} classification={self.classification!r} "
            f"score={self.operational_score} captured_at={self.captured_at}>"
        )
