"""Gather quant/adaptive intelligence data for the 6h summary.

Queries TradingSignalOutcome directly — no external ML, no LLM.
All metrics are deterministic aggregations (win_rate, expectancy, PF, etc.).
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.trading.validation.models import TradingSignalOutcome
from app.telegram_summary.dto import QuantSummaryPayload

logger = logging.getLogger(__name__)


def _compute_stats(rows: list[Any]) -> dict[str, float | None]:
    """Compute win_rate, expectancy, profit_factor, avg_return_pct, max_drawdown_pct.

    Args:
        rows: list of TradingSignalOutcome instances (outcome_correct is not None).

    Returns:
        Dict with keys: win_rate, expectancy, profit_factor, avg_return_pct,
        max_drawdown_pct.  All values are None when there is no data.
    """
    _empty: dict[str, float | None] = {
        "win_rate": None,
        "expectancy": None,
        "profit_factor": None,
        "avg_return_pct": None,
        "max_drawdown_pct": None,
    }
    if not rows:
        return _empty

    total = len(rows)
    wins = sum(1 for r in rows if r.outcome_correct)
    win_rate = wins / total

    gains = [
        float(r.price_change_pct)
        for r in rows
        if r.outcome_correct and r.price_change_pct is not None
    ]
    losses = [
        abs(float(r.price_change_pct))
        for r in rows
        if not r.outcome_correct and r.price_change_pct is not None
    ]

    avg_gain = sum(gains) / len(gains) if gains else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    expectancy = (win_rate * avg_gain) - ((1.0 - win_rate) * avg_loss)

    total_gains = sum(gains)
    total_losses = sum(losses)
    profit_factor: float | None = (total_gains / total_losses) if total_losses > 0 else None

    all_returns = [
        float(r.price_change_pct)
        for r in rows
        if r.price_change_pct is not None
    ]
    avg_return_pct = (sum(all_returns) / len(all_returns)) if all_returns else None

    maes = [float(r.max_adverse_pct) for r in rows if r.max_adverse_pct is not None]
    max_drawdown_pct = max(maes) if maes else None

    return {
        "win_rate": win_rate,
        "expectancy": expectancy,
        "profit_factor": profit_factor,
        "avg_return_pct": avg_return_pct,
        "max_drawdown_pct": max_drawdown_pct,
    }


class QuantSummaryService:
    """Query TradingSignalOutcome and compute quant metrics for the 6h summary."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def gather(self, lookback_days: int = 30) -> QuantSummaryPayload:
        since = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        rows = list(
            self._db.execute(
                select(TradingSignalOutcome).where(
                    TradingSignalOutcome.signal_at >= since,
                    TradingSignalOutcome.outcome_correct.is_not(None),
                )
            ).scalars().all()
        )

        stats = _compute_stats(rows)

        # Dominant regime
        regimes = [r.regime for r in rows if r.regime]
        dominant_regime: str | None = Counter(regimes).most_common(1)[0][0] if regimes else None

        # Top symbols by win rate (require ≥5 outcomes to rank)
        symbol_rows: dict[str, list[Any]] = {}
        for r in rows:
            symbol_rows.setdefault(r.symbol, []).append(r)

        top_symbols = sorted(
            [s for s, sr in symbol_rows.items() if len(sr) >= 5],
            key=lambda s: sum(1 for r in symbol_rows[s] if r.outcome_correct) / len(symbol_rows[s]),
            reverse=True,
        )[:3]

        # Derive risk level and recommendation from win_rate
        wr = stats["win_rate"]
        pf = stats.get("profit_factor") or 0.0

        if wr is None or len(rows) < 10:
            risk_level = "LOW"
            recommendation = "OBSERVE_ONLY"
        elif wr >= 0.60:
            risk_level = "LOW"
            recommendation = "BOOST" if pf >= 1.5 else "KEEP"
        elif wr >= 0.50:
            risk_level = "MEDIUM"
            recommendation = "KEEP"
        elif wr >= 0.40:
            risk_level = "HIGH"
            recommendation = "THROTTLE"
        else:
            risk_level = "CRITICAL"
            recommendation = "DISABLE"

        boost_blocked = (
            risk_level != "LOW"
            or pf < 1.5
            or len(rows) < 30
        )

        return QuantSummaryPayload(
            total_outcomes=len(rows),
            lookback_days=lookback_days,
            win_rate=stats["win_rate"],
            expectancy=stats["expectancy"],
            profit_factor=stats["profit_factor"],
            avg_return_pct=stats["avg_return_pct"],
            max_drawdown_pct=stats["max_drawdown_pct"],
            dominant_regime=dominant_regime,
            top_symbols=top_symbols,
            overall_recommendation=recommendation,
            risk_level=risk_level,
            boost_blocked=boost_blocked,
            calibrated=wr is not None and wr >= 0.55,
        )
