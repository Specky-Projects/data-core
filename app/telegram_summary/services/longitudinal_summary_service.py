"""Gather longitudinal comparison data (24h vs 7d) for the daily summary.

Queries TradingSignalOutcome for two windows and computes stats for each.
Reuses _compute_stats from quant_summary_service — no duplication.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.trading.validation.models import TradingSignalOutcome
from app.telegram_summary.dto import LongitudinalSummaryPayload
from app.telegram_summary.services.quant_summary_service import _compute_stats

logger = logging.getLogger(__name__)


def _dominant_regime(rows: list[Any]) -> str | None:
    regimes = [r.regime for r in rows if r.regime]
    return Counter(regimes).most_common(1)[0][0] if regimes else None


def _fetch_outcomes(db: Session, since: datetime) -> list[Any]:
    return list(
        db.execute(
            select(TradingSignalOutcome).where(
                TradingSignalOutcome.signal_at >= since,
                TradingSignalOutcome.outcome_correct.is_not(None),
            )
        ).scalars().all()
    )


class LongitudinalSummaryService:
    """Compare 24h vs 7d windows of TradingSignalOutcome data."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def gather(self) -> LongitudinalSummaryPayload:
        now = datetime.now(timezone.utc)
        rows_24h = _fetch_outcomes(self._db, now - timedelta(hours=24))
        rows_7d = _fetch_outcomes(self._db, now - timedelta(days=7))

        s24 = _compute_stats(rows_24h)
        s7d = _compute_stats(rows_7d)

        return LongitudinalSummaryPayload(
            outcomes_24h=len(rows_24h),
            outcomes_7d=len(rows_7d),
            win_rate_24h=s24["win_rate"],
            win_rate_7d=s7d["win_rate"],
            expectancy_24h=s24["expectancy"],
            expectancy_7d=s7d["expectancy"],
            profit_factor_24h=s24["profit_factor"],
            profit_factor_7d=s7d["profit_factor"],
            max_drawdown_24h=s24["max_drawdown_pct"],
            max_drawdown_7d=s7d["max_drawdown_pct"],
            dominant_regime_24h=_dominant_regime(rows_24h),
            dominant_regime_7d=_dominant_regime(rows_7d),
        )
