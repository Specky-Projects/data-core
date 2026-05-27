"""StrategyFeedbackEngine — per-slice win rate, expectancy, drawdown analysis.

Advisory-only: reads TradingSignalOutcome rows, never writes trading decisions.

Slice key: "{symbol}|{timeframe}|{regime or 'any'}|{signal}"
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.adaptive_intelligence.dto import (
    Recommendation,
    StrategyFeedbackResult,
    StrategySlice,
    _classify_recommendation,
)
from app.modules.trading.validation.models import TradingSignalOutcome

logger = logging.getLogger(__name__)


# ── Internal accumulator ───────────────────────────────────────────────────────

class _Acc:
    """Accumulates raw numbers for one slice."""

    __slots__ = (
        "wins", "losses", "returns", "drawdowns",
        "gross_profit", "gross_loss", "mfe", "mae",
    )

    def __init__(self) -> None:
        self.wins: int = 0
        self.losses: int = 0
        self.returns: list[float] = []
        self.drawdowns: list[float] = []
        self.gross_profit: float = 0.0
        self.gross_loss: float = 0.0
        self.mfe: list[float] = []
        self.mae: list[float] = []

    # ------------------------------------------------------------------

    def add(self, outcome: TradingSignalOutcome) -> None:
        ret = float(outcome.price_change_pct or 0.0)
        self.returns.append(ret)
        if ret > 0:
            self.gross_profit += ret
            self.wins += 1
        else:
            self.gross_loss += abs(ret)
            self.losses += 1
        # worst adverse excursion per outcome → drawdown proxy
        adverse = float(outcome.max_adverse_pct or 0.0)
        self.drawdowns.append(abs(adverse))
        if outcome.max_favorable_pct is not None:
            self.mfe.append(float(outcome.max_favorable_pct))
        if outcome.max_adverse_pct is not None:
            self.mae.append(abs(float(outcome.max_adverse_pct)))

    # ------------------------------------------------------------------

    @property
    def sample_size(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        n = self.sample_size
        return self.wins / n if n else 0.0

    @property
    def avg_return_pct(self) -> float:
        return sum(self.returns) / len(self.returns) if self.returns else 0.0

    @property
    def expectancy(self) -> float:
        """win_rate * avg_win - loss_rate * avg_loss."""
        n = self.sample_size
        if n == 0:
            return 0.0
        avg_win = (self.gross_profit / self.wins) if self.wins else 0.0
        avg_loss = (self.gross_loss / self.losses) if self.losses else 0.0
        return self.win_rate * avg_win - (1 - self.win_rate) * avg_loss

    @property
    def max_drawdown_pct(self) -> float:
        return max(self.drawdowns) if self.drawdowns else 0.0

    @property
    def profit_factor(self) -> float | None:
        if self.gross_loss == 0:
            return None  # no losses → undefined, not ∞
        return self.gross_profit / self.gross_loss

    @property
    def avg_mfe_pct(self) -> float | None:
        return sum(self.mfe) / len(self.mfe) if self.mfe else None

    @property
    def avg_mae_pct(self) -> float | None:
        return sum(self.mae) / len(self.mae) if self.mae else None


# ── Slice key helper ───────────────────────────────────────────────────────────

def _slice_key(symbol: str, timeframe: str, regime: str | None, signal: str) -> str:
    return f"{symbol}|{timeframe}|{regime or 'any'}|{signal}"


def _build_reason(
    rec: Recommendation,
    win_rate: float,
    expectancy: float,
    profit_factor: float | None,
    sample_size: int,
) -> str:
    pf_str = f"{profit_factor:.2f}" if profit_factor is not None else "N/A"
    base = (
        f"n={sample_size} wr={win_rate:.1%} "
        f"exp={expectancy:.4f} pf={pf_str}"
    )
    notes: dict[str, str] = {
        "OBSERVE_ONLY": "insufficient sample to conclude",
        "BOOST": "strong win rate, positive expectancy, healthy profit factor",
        "KEEP": "acceptable win rate and non-negative expectancy",
        "DISABLE": "poor win rate + negative expectancy + adequate sample",
        "THROTTLE": "marginal performance — monitor closely",
    }
    return f"{notes.get(rec, '')} ({base})"


# ── Engine ─────────────────────────────────────────────────────────────────────

class StrategyFeedbackEngine:
    """Analyses historical TradingSignalOutcome rows by slice.

    Parameters
    ----------
    db:
        Active SQLAlchemy Session.
    lookback_days:
        How many calendar days of outcomes to include (default: 30).
    """

    def __init__(self, db: Session, lookback_days: int = 30) -> None:
        self._db = db
        self._lookback_days = lookback_days

    # ------------------------------------------------------------------

    def evaluate(self) -> StrategyFeedbackResult:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._lookback_days)

        rows: list[TradingSignalOutcome] = (
            self._db.query(TradingSignalOutcome)
            .filter(
                TradingSignalOutcome.signal_at >= cutoff,
                TradingSignalOutcome.outcome_correct.isnot(None),
                TradingSignalOutcome.price_change_pct.isnot(None),
            )
            .all()
        )

        # Accumulate per slice
        accs: dict[str, _Acc] = defaultdict(_Acc)
        meta: dict[str, tuple[str, str, str | None, str]] = {}  # key → (symbol, tf, regime, signal)

        for row in rows:
            key = _slice_key(row.symbol, row.timeframe, row.regime, row.signal)
            accs[key].add(row)
            meta[key] = (row.symbol, row.timeframe, row.regime, row.signal)

        # Build slices
        slices: list[StrategySlice] = []
        summary: dict[str, int] = {
            "BOOST": 0, "KEEP": 0, "THROTTLE": 0, "DISABLE": 0, "OBSERVE_ONLY": 0,
        }
        top_performers: list[str] = []
        underperformers: list[str] = []

        for key, acc in accs.items():
            symbol, timeframe, regime, signal = meta[key]
            rec = _classify_recommendation(
                acc.win_rate, acc.expectancy, acc.profit_factor, acc.sample_size
            )
            reason = _build_reason(
                rec, acc.win_rate, acc.expectancy, acc.profit_factor, acc.sample_size
            )
            slices.append(StrategySlice(
                symbol=symbol,
                timeframe=timeframe,
                regime=regime,
                signal=signal,
                sample_size=acc.sample_size,
                win_rate=acc.win_rate,
                avg_return_pct=acc.avg_return_pct,
                expectancy=acc.expectancy,
                max_drawdown_pct=acc.max_drawdown_pct,
                profit_factor=acc.profit_factor,
                avg_mfe_pct=acc.avg_mfe_pct,
                avg_mae_pct=acc.avg_mae_pct,
                recommendation=rec,
                recommendation_reason=reason,
            ))
            summary[rec] = summary.get(rec, 0) + 1
            if rec == "BOOST":
                top_performers.append(key)
            elif rec in ("THROTTLE", "DISABLE"):
                underperformers.append(key)

        logger.info(
            "adaptive.strategy_feedback evaluated",
            extra={
                "lookback_days": self._lookback_days,
                "total_outcomes": len(rows),
                "slices": len(slices),
                "summary": summary,
            },
        )

        return StrategyFeedbackResult(
            evaluated_at=datetime.now(timezone.utc),
            lookback_days=self._lookback_days,
            total_outcomes=len(rows),
            slices=slices,
            summary=summary,
            top_performers=top_performers,
            underperformers=underperformers,
        )
