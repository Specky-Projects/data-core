"""SQLAlchemy model for edge alert state — Phase 10."""
from __future__ import annotations

import uuid

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from database.models import Base


class EdgeAlertState(Base):
    """One row per alert key — persists last-sent state for dedup and change detection.

    Keys used:
    - ``daily_summary``           — date of last daily summary sent
    - ``weekly_report``           — ISO week of last weekly report sent
    - ``gate_24h``, ``gate_72h``, ``gate_168h``  — last n seen per horizon
    - ``edge_status_24h``, ``edge_status_72h``, ``edge_status_168h``
    - ``wr_alert_24h``, etc.      — WR / PF alert last value
    """

    __tablename__ = "edge_alert_state"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    alert_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    last_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_sent_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
