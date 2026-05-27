"""RegimeAdapter — cross-analyses signal performance by market regime.

Groups TradingSignalOutcome rows by (regime, signal, symbol, timeframe) and
produces per-combination recommendations using the same classification logic
as StrategyFeedbackEngine.

Advisory-only: reads TradingSignalOutcome rows, never writes.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.adaptive_intelligence.dto import (
    RegimeAdaptation,
    RegimeAdapterResult,
    _classify_recommendation,
)
from app.modules.trading.validation.models import TradingSignalOutcome

logger = logging.getLogger(__name__)


# ── Accumulator (reuses same maths as strategy_feedback) ──────────────────────

class _Acc:
    __slots__ = ("wins", "losses", "returns", "gross_profit", "gross_loss")

    def __init__(self) -> None:
        self.wins = 0
        self.losses = 0
        self.returns: list[float] = []
        self.gross_profit = 0.0
        self.gross_loss = 0.0

    def add(self, ret: float) -> None:
        self.returns.append(ret)
        if ret > 0:
            self.wins += 1
            self.gross_profit += ret
        else:
            self.losses += 1
            self.gross_loss += abs(ret)

    @property
    def sample_size(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        n = self.sample_size
        return self.wins / n if n else 0.0

    @property
    def expectancy(self) -> float:
        n = self.sample_size
        if n == 0:
            return 0.0
        avg_win = (self.gross_profit / self.wins) if self.wins else 0.0
        avg_loss = (self.gross_loss / self.losses) if self.losses else 0.0
        return self.win_rate * avg_win - (1 - self.win_rate) * avg_loss

    @property
    def profit_factor(self) -> float | None:
        if self.gross_loss == 0:
            return None
        return self.gross_profit / self.gross_loss


def _build_reason(rec: str, wr: float, exp: float, n: int, regime: str, signal: str) -> str:
    return (
        f"regime='{regime}' signal={signal}: "
        f"n={n} wr={wr:.1%} exp={exp:.4f} → {rec}"
    )


# ── Engine ─────────────────────────────────────────────────────────────────────

class RegimeAdapter:
    """Produce per-regime adaptation recommendations.

    Parameters
    ----------
    db:
        Active SQLAlchemy Session.
    lookback_days:
        Calendar days of outcomes to include (default: 30).
    """

    def __init__(self, db: Session, lookback_days: int = 30) -> None:
        self._db = db
        self._lookback_days = lookback_days

    # ------------------------------------------------------------------

    def evaluate(self) -> RegimeAdapterResult:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._lookback_days)

        rows: list[TradingSignalOutcome] = (
            self._db.query(TradingSignalOutcome)
            .filter(
                TradingSignalOutcome.signal_at >= cutoff,
                TradingSignalOutcome.outcome_correct.isnot(None),
                TradingSignalOutcome.price_change_pct.isnot(None),
                TradingSignalOutcome.regime.isnot(None),
            )
            .all()
        )

        # Per-adaptation accumulator: (regime, signal, symbol, timeframe)
        detail_accs: dict[tuple[str, str, str, str], _Acc] = defaultdict(_Acc)
        # Per-regime aggregate: regime → _Acc (for distribution + dominant)
        regime_accs: dict[str, _Acc] = defaultdict(_Acc)
        regime_counts: dict[str, int] = defaultdict(int)

        for row in rows:
            regime = row.regime or "unknown"
            symbol = row.symbol
            timeframe = row.timeframe
            signal = row.signal
            ret = float(row.price_change_pct or 0.0)

            detail_accs[(regime, signal, symbol, timeframe)].add(ret)
            regime_accs[regime].add(ret)
            regime_counts[regime] += 1

        # Build RegimeAdaptation list
        adaptations: list[RegimeAdaptation] = []
        for (regime, signal, symbol, timeframe), acc in detail_accs.items():
            rec = _classify_recommendation(
                acc.win_rate, acc.expectancy, acc.profit_factor, acc.sample_size
            )
            reason = _build_reason(rec, acc.win_rate, acc.expectancy, acc.sample_size, regime, signal)
            adaptations.append(RegimeAdaptation(
                regime=regime,
                signal=signal,
                symbol=symbol,
                timeframe=timeframe,
                sample_size=acc.sample_size,
                win_rate=acc.win_rate,
                expectancy=acc.expectancy,
                recommendation=rec,
                reason=reason,
            ))

        # Dominant regime = regime with most outcomes
        dominant_regime: str | None = None
        if regime_counts:
            dominant_regime = max(regime_counts, key=lambda r: regime_counts[r])

        regimes_observed = sorted(regime_counts.keys())
        regime_distribution = dict(regime_counts)

        # Per-regime aggregate performance summary
        per_regime_performance: dict[str, dict[str, Any]] = {}
        for regime, acc in regime_accs.items():
            per_regime_performance[regime] = {
                "sample_size": acc.sample_size,
                "win_rate": round(acc.win_rate, 4),
                "expectancy": round(acc.expectancy, 4),
                "profit_factor": round(acc.profit_factor, 4) if acc.profit_factor is not None else None,
            }

        logger.info(
            "adaptive.regime_adapter evaluated",
            extra={
                "lookback_days": self._lookback_days,
                "total_outcomes": len(rows),
                "adaptations": len(adaptations),
                "regimes_observed": regimes_observed,
                "dominant_regime": dominant_regime,
            },
        )

        return RegimeAdapterResult(
            evaluated_at=datetime.now(timezone.utc),
            adaptations=adaptations,
            regimes_observed=regimes_observed,
            dominant_regime=dominant_regime,
            regime_distribution=regime_distribution,
            per_regime_performance=per_regime_performance,
        )
