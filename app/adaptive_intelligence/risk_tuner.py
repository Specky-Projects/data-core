"""RiskTuner — derives position-size, confidence thresholds, and policy hints.

Consumes the outputs of the three analysis engines and produces a
RiskTuningResult that can be fed directly into the Enforcement
PolicyContract generator as `policy_hints`.

Advisory-only: never writes to trading tables.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.adaptive_intelligence.dto import (
    ConfidenceCalibrationResult,
    RegimeAdapterResult,
    RiskTuningResult,
    StrategyFeedbackResult,
)
from app.modules.trading.validation.models import TradingSignalOutcome

logger = logging.getLogger(__name__)

RiskLevel = Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]

# Thresholds used to derive risk level from recent aggregate metrics
_WIN_RATE_CRITICAL = 0.35
_WIN_RATE_HIGH = 0.45
_WIN_RATE_MODERATE = 0.55

_EXPECTANCY_CRITICAL = -0.30
_EXPECTANCY_HIGH = -0.10
_EXPECTANCY_MODERATE = 0.0

_DRAWDOWN_CRITICAL = 15.0   # %
_DRAWDOWN_HIGH = 8.0
_DRAWDOWN_MODERATE = 4.0

# Position size multiplier per risk level
_SIZE_BY_RISK: dict[str, float] = {
    "LOW": 1.0,
    "MODERATE": 0.75,
    "HIGH": 0.50,
    "CRITICAL": 0.25,
}

# Min-confidence hint per risk level (override if calibration provides better)
_CONF_BY_RISK: dict[str, int] = {
    "LOW": 55,
    "MODERATE": 60,
    "HIGH": 65,
    "CRITICAL": 75,
}


class RiskTuner:
    """Derive risk level and policy hints from combined engine outputs.

    Parameters
    ----------
    db:
        Active SQLAlchemy Session.
    lookback_days:
        Calendar days of outcomes to use for recent aggregate stats (default: 14).
    """

    def __init__(self, db: Session, lookback_days: int = 14) -> None:
        self._db = db
        self._lookback_days = lookback_days

    # ------------------------------------------------------------------

    def evaluate(
        self,
        strategy: StrategyFeedbackResult,
        calibration: ConfidenceCalibrationResult,
        regime: RegimeAdapterResult,
    ) -> RiskTuningResult:
        # ── Aggregate recent metrics from DB ──────────────────────────────────
        wr, exp, pf, max_dd = self._fetch_recent_aggregates()

        # ── Derive risk level ─────────────────────────────────────────────────
        risk_level, reasoning = self._classify_risk(wr, exp, pf, max_dd, strategy, calibration)

        # ── Position size multiplier ──────────────────────────────────────────
        size_multiplier = _SIZE_BY_RISK[risk_level]

        # ── Min confidence threshold ──────────────────────────────────────────
        # Prefer the calibrated threshold from CalibrationEngine if available
        min_conf = _CONF_BY_RISK[risk_level]
        if calibration.recommended_min_confidence is not None:
            # Take the more conservative of the two
            min_conf = max(min_conf, calibration.recommended_min_confidence)

        # ── Throttle / disable flags ──────────────────────────────────────────
        disable_pct = (
            strategy.summary.get("DISABLE", 0) / max(len(strategy.slices), 1)
        )
        throttle_pct = (
            (strategy.summary.get("THROTTLE", 0) + strategy.summary.get("DISABLE", 0))
            / max(len(strategy.slices), 1)
        )
        throttle_recommended = risk_level in ("HIGH", "CRITICAL") or throttle_pct >= 0.50
        disable_recommended = risk_level == "CRITICAL" or disable_pct >= 0.50

        # ── Policy hints (consumed by PolicyContract generator) ───────────────
        policy_hints: dict[str, Any] = {
            "source": "adaptive_intelligence",
            "risk_level": risk_level,
            "suggested_position_size_multiplier": size_multiplier,
            "suggested_min_confidence": min_conf,
            "throttle_recommended": throttle_recommended,
            "disable_recommended": disable_recommended,
            "dominant_regime": regime.dominant_regime,
            "well_calibrated": calibration.well_calibrated,
            "overconfidence_warning": calibration.overconfidence_warning,
            "top_performers": strategy.top_performers[:5],
            "underperformers": strategy.underperformers[:5],
        }

        logger.info(
            "adaptive.risk_tuner evaluated",
            extra={
                "risk_level": risk_level,
                "size_multiplier": size_multiplier,
                "min_confidence": min_conf,
                "throttle_recommended": throttle_recommended,
                "disable_recommended": disable_recommended,
            },
        )

        return RiskTuningResult(
            evaluated_at=datetime.now(timezone.utc),
            current_win_rate=wr,
            current_expectancy=exp,
            current_profit_factor=pf,
            max_observed_drawdown_pct=max_dd,
            suggested_position_size_multiplier=size_multiplier,
            suggested_min_confidence=min_conf,
            risk_level=risk_level,
            throttle_recommended=throttle_recommended,
            disable_recommended=disable_recommended,
            reasoning=reasoning,
            policy_hints=policy_hints,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fetch_recent_aggregates(
        self,
    ) -> tuple[float | None, float | None, float | None, float | None]:
        """Compute recent aggregate win_rate, expectancy, profit_factor, max_drawdown."""
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

        if not rows:
            return None, None, None, None

        wins = sum(1 for r in rows if r.outcome_correct)
        n = len(rows)
        wr = wins / n

        returns = [float(r.price_change_pct) for r in rows]
        gross_profit = sum(r for r in returns if r > 0)
        gross_loss = abs(sum(r for r in returns if r < 0))
        n_wins = sum(1 for r in returns if r > 0)
        n_loss = sum(1 for r in returns if r <= 0)

        avg_win = gross_profit / n_wins if n_wins else 0.0
        avg_loss = gross_loss / n_loss if n_loss else 0.0
        exp = wr * avg_win - (1 - wr) * avg_loss
        pf = (gross_profit / gross_loss) if gross_loss > 0 else None

        adverse_vals = [abs(float(r.max_adverse_pct)) for r in rows if r.max_adverse_pct is not None]
        max_dd = max(adverse_vals) if adverse_vals else None

        return wr, exp, pf, max_dd

    @staticmethod
    def _classify_risk(
        wr: float | None,
        exp: float | None,
        pf: float | None,
        max_dd: float | None,
        strategy: StrategyFeedbackResult,
        calibration: ConfidenceCalibrationResult,
    ) -> tuple[RiskLevel, list[str]]:
        reasoning: list[str] = []

        if wr is None:
            reasoning.append("insufficient recent data — defaulting to MODERATE risk")
            return "MODERATE", reasoning

        # ── Win rate assessment ───────────────────────────────────────────────
        if wr < _WIN_RATE_CRITICAL:
            reasoning.append(f"win_rate={wr:.1%} below critical threshold ({_WIN_RATE_CRITICAL:.0%})")
            risk_wr: RiskLevel = "CRITICAL"
        elif wr < _WIN_RATE_HIGH:
            reasoning.append(f"win_rate={wr:.1%} below high-risk threshold ({_WIN_RATE_HIGH:.0%})")
            risk_wr = "HIGH"
        elif wr < _WIN_RATE_MODERATE:
            reasoning.append(f"win_rate={wr:.1%} below moderate threshold ({_WIN_RATE_MODERATE:.0%})")
            risk_wr = "MODERATE"
        else:
            reasoning.append(f"win_rate={wr:.1%} acceptable")
            risk_wr = "LOW"

        # ── Expectancy assessment ─────────────────────────────────────────────
        exp_val = exp or 0.0
        if exp_val < _EXPECTANCY_CRITICAL:
            reasoning.append(f"expectancy={exp_val:.4f} critically negative")
            risk_exp: RiskLevel = "CRITICAL"
        elif exp_val < _EXPECTANCY_HIGH:
            reasoning.append(f"expectancy={exp_val:.4f} negative")
            risk_exp = "HIGH"
        elif exp_val < _EXPECTANCY_MODERATE:
            reasoning.append(f"expectancy={exp_val:.4f} slightly negative")
            risk_exp = "MODERATE"
        else:
            reasoning.append(f"expectancy={exp_val:.4f} non-negative")
            risk_exp = "LOW"

        # ── Drawdown assessment ───────────────────────────────────────────────
        dd = max_dd or 0.0
        if dd >= _DRAWDOWN_CRITICAL:
            reasoning.append(f"max_drawdown={dd:.1f}% critical")
            risk_dd: RiskLevel = "CRITICAL"
        elif dd >= _DRAWDOWN_HIGH:
            reasoning.append(f"max_drawdown={dd:.1f}% high")
            risk_dd = "HIGH"
        elif dd >= _DRAWDOWN_MODERATE:
            reasoning.append(f"max_drawdown={dd:.1f}% moderate")
            risk_dd = "MODERATE"
        else:
            risk_dd = "LOW"

        # ── Calibration penalty ───────────────────────────────────────────────
        if calibration.overconfidence_warning:
            reasoning.append("overconfidence warning: model scores exceed realized win rate")

        # ── Aggregate: take the worst single dimension ────────────────────────
        _ORDER = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}
        worst = max([risk_wr, risk_exp, risk_dd], key=lambda r: _ORDER[r])

        # Bump up one level if overconfidence detected and not already CRITICAL
        if calibration.overconfidence_warning and worst != "CRITICAL":
            levels = ["LOW", "MODERATE", "HIGH", "CRITICAL"]
            worst = levels[min(_ORDER[worst] + 1, 3)]  # type: ignore[assignment]
            reasoning.append("risk level elevated one tier due to overconfidence warning")

        return worst, reasoning  # type: ignore[return-value]
