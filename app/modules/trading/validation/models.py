"""SQLAlchemy model for retrospective trading signal outcomes.

Each row records the result of evaluating a BUY or SELL signal N candles after
it was generated, measuring whether the price moved in the predicted direction.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database.models import Base


class TradingSignalOutcome(Base):
    __tablename__ = "trading_signal_outcomes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # FK to trading_analytics — nullable to survive analytics row deletions.
    analytics_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trading_analytics.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )

    # Signal context (denormalised for query efficiency)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(20), nullable=False)
    signal: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # BUY | SELL
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    regime: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # Signal candle
    signal_price: Mapped[float | None] = mapped_column(
        Numeric(24, 8), nullable=True, comment="Close price at signal candle"
    )
    signal_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Outcome candle (after evaluation_horizon_candles)
    outcome_price: Mapped[float | None] = mapped_column(
        Numeric(24, 8), nullable=True, comment="Close price at evaluation horizon"
    )
    outcome_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    candles_elapsed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Outcome metrics
    price_change_pct: Mapped[float | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="(outcome_price - signal_price) / signal_price × 100",
    )
    max_favorable_pct: Mapped[float | None] = mapped_column(
        Numeric(10, 4), nullable=True, comment="MFE: max favourable excursion during horizon"
    )
    max_adverse_pct: Mapped[float | None] = mapped_column(
        Numeric(10, 4), nullable=True, comment="MAE: max adverse excursion during horizon"
    )
    outcome_correct: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        index=True,
        comment="True when price moved in the signal direction",
    )

    evaluation_horizon_candles: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=6,
        comment="Number of subsequent candles used for evaluation",
    )

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
