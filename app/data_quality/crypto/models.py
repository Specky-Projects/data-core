"""SQLAlchemy model for crypto dataset quality scores.

Each row represents one integrity evaluation for a (symbol, timeframe) pair,
capturing freshness, coverage, and OHLC consistency sub-scores alongside the
composite 0-100 integrity score.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database.models import Base


class CryptoDatasetQualityScore(Base):
    __tablename__ = "crypto_dataset_quality_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Composite 0-100 score
    integrity_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    # Sub-scores
    freshness_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True, comment="0-40 pts")
    coverage_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True, comment="0-40 pts")
    ohlc_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True, comment="0-20 pts")

    # Raw measurements
    staleness_hours: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    coverage_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    gap_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_candles_24h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_candles_24h: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Full component breakdown for forensics
    components_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
