"""RegimeAdapter — cross-analyses signal performance by market regime.

Groups TradingSignalOutcome rows by (regime, signal, symbol, timeframe) and
produces per-combination recommendations using the same classification logic
as StrategyFeedbackEngine.

Advisory-only: reads TradingSignalOutcome rows, never writes.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.adaptive_intelligence.dto import (
    EvaluationContext,
    RegimeAdaptation,
    RegimeAdapterResult,
    ScientificVersionMetadata,
    _classify_recommendation,
    build_decision_hash,
    build_feature_provenance,
    derive_evaluation_context,
    filter_rows_for_context,
)
from app.modules.trading.validation.models import TradingSignalOutcome

logger = logging.getLogger(__name__)


# ── Accumulator (reuses same maths as strategy_feedback) ──────────────────────

class _Acc:
    __slots__ = ("wins", "losses", "returns", "gross_profit", "gross_loss", "evidence_ids")

    def __init__(self) -> None:
        self.wins = 0
        self.losses = 0
        self.returns: list[float] = []
        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.evidence_ids: list[str] = []

    def add(self, ret: float, evidence_id: str | None = None) -> None:
        self.returns.append(ret)
        if evidence_id is not None:
            self.evidence_ids.append(evidence_id)
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

    def __init__(
        self,
        db: Session,
        lookback_days: int = 30,
        evaluation_context: EvaluationContext | None = None,
    ) -> None:
        self._db = db
        self._lookback_days = lookback_days
        self._evaluation_context = evaluation_context

    # ------------------------------------------------------------------

    def evaluate(self) -> RegimeAdapterResult:
        all_rows: list[TradingSignalOutcome] = (
            self._db.query(TradingSignalOutcome)
            .filter(
                TradingSignalOutcome.outcome_correct.isnot(None),
                TradingSignalOutcome.price_change_pct.isnot(None),
                TradingSignalOutcome.regime.isnot(None),
            )
            .all()
        )
        evaluation_context = derive_evaluation_context(
            all_rows,
            self._lookback_days,
            self._evaluation_context,
        )
        rows = filter_rows_for_context(all_rows, evaluation_context, self._lookback_days)

        # Per-adaptation accumulator: (regime, signal, symbol, timeframe)
        detail_accs: dict[tuple[str, str, str, str], _Acc] = defaultdict(_Acc)
        # Per-regime aggregate: regime → _Acc (for distribution + dominant)
        regime_accs: dict[str, _Acc] = defaultdict(_Acc)
        regime_counts: dict[str, int] = defaultdict(int)

        versions = ScientificVersionMetadata()

        for row in rows:
            regime = row.regime or "unknown"
            symbol = row.symbol
            timeframe = row.timeframe
            signal = row.signal
            ret = float(row.price_change_pct or 0.0)
            evidence_id = str(row.id) if getattr(row, "id", None) is not None else None

            detail_accs[(regime, signal, symbol, timeframe)].add(ret, evidence_id)
            regime_accs[regime].add(ret, evidence_id)
            regime_counts[regime] += 1

        # Build RegimeAdaptation list
        adaptations: list[RegimeAdaptation] = []
        for (regime, signal, symbol, timeframe), acc in detail_accs.items():
            rec = _classify_recommendation(
                acc.win_rate, acc.expectancy, acc.profit_factor, acc.sample_size
            )
            reason = _build_reason(
                rec,
                acc.win_rate,
                acc.expectancy,
                acc.sample_size,
                regime,
                signal,
            )
            entity_id = f"{regime}|{signal}|{symbol or 'all'}|{timeframe or 'all'}"
            provenance = build_feature_provenance(
                evaluation_context=evaluation_context,
                entity_id=entity_id,
                features={
                    "win_rate": acc.win_rate,
                    "expectancy": acc.expectancy,
                    "sample_size": acc.sample_size,
                    "regime": regime,
                    "signal": signal,
                    "recommendation": rec,
                },
                evidence_ids=acc.evidence_ids,
                versions=versions,
            )
            decision_hash = build_decision_hash(
                evaluation_context=evaluation_context,
                versions=versions,
                provenance=provenance,
                entity_id=entity_id,
                recommendation=rec,
            )
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
                evidence_ids=sorted(acc.evidence_ids)[:25],
                versions=versions,
                provenance=provenance,
                decision_hash=decision_hash,
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
                "profit_factor": (
                    round(acc.profit_factor, 4)
                    if acc.profit_factor is not None
                    else None
                ),
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
            evaluated_at=evaluation_context.evaluation_timestamp,
            adaptations=adaptations,
            regimes_observed=regimes_observed,
            dominant_regime=dominant_regime,
            regime_distribution=regime_distribution,
            per_regime_performance=per_regime_performance,
        )
