"""DTOs for the Adaptive Intelligence Layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ── Recommendation enum ────────────────────────────────────────────────────────

Recommendation = Literal["KEEP", "THROTTLE", "DISABLE", "BOOST", "OBSERVE_ONLY"]

# Minimum samples required before any non-OBSERVE_ONLY recommendation.
MIN_SAMPLE_FOR_RECOMMENDATION = 10
MIN_SAMPLE_FOR_BOOST = 30
MIN_SAMPLE_FOR_DISABLE = 20


def _classify_recommendation(
    win_rate: float,
    expectancy: float,
    profit_factor: float | None,
    sample_size: int,
) -> Recommendation:
    if sample_size < MIN_SAMPLE_FOR_RECOMMENDATION:
        return "OBSERVE_ONLY"
    pf = profit_factor or 0.0
    if win_rate >= 0.60 and expectancy > 0 and pf >= 1.5 and sample_size >= MIN_SAMPLE_FOR_BOOST:
        return "BOOST"
    if win_rate >= 0.50 and expectancy >= 0:
        return "KEEP"
    if win_rate < 0.40 and expectancy < -0.1 and sample_size >= MIN_SAMPLE_FOR_DISABLE:
        return "DISABLE"
    return "THROTTLE"


# ── Strategy Feedback ──────────────────────────────────────────────────────────

class StrategySlice(BaseModel):
    """Performance metrics for one (symbol, timeframe, regime, signal) slice."""
    symbol: str
    timeframe: str
    regime: str | None
    signal: str  # BUY | SELL
    sample_size: int
    win_rate: float = Field(ge=0.0, le=1.0)
    avg_return_pct: float
    expectancy: float      # win_rate * avg_win - loss_rate * avg_loss
    max_drawdown_pct: float
    profit_factor: float | None  # gross_profit / gross_loss; None if no losses
    avg_mfe_pct: float | None   # mean Maximum Favorable Excursion
    avg_mae_pct: float | None   # mean Maximum Adverse Excursion
    recommendation: Recommendation
    recommendation_reason: str


class StrategyFeedbackResult(BaseModel):
    evaluated_at: datetime
    lookback_days: int
    total_outcomes: int
    slices: list[StrategySlice]
    summary: dict[str, int]   # {KEEP: N, THROTTLE: N, ...}
    top_performers: list[str]   # slice keys worth boosting
    underperformers: list[str]  # slice keys needing throttle/disable


# ── Confidence Calibration ─────────────────────────────────────────────────────

class CalibrationBucket(BaseModel):
    """One confidence bucket (e.g. 61-80)."""
    label: str
    lower: int
    upper: int
    sample_size: int
    predicted_confidence_avg: float   # mean confidence score in this bucket
    realized_win_rate: float          # fraction of outcomes that were correct
    calibration_gap: float            # realized_win_rate - predicted_confidence_avg/100
    avg_return_pct: float
    overconfident: bool               # predicted >> realized
    underconfident: bool              # predicted << realized


class ConfidenceCalibrationResult(BaseModel):
    evaluated_at: datetime
    total_outcomes: int
    buckets: list[CalibrationBucket]
    calibrated_threshold: int | None  # lowest confidence where win_rate >= 55 %
    overall_calibration_slope: float | None  # positive = well calibrated
    well_calibrated: bool
    overconfidence_warning: bool
    underconfidence_warning: bool
    recommended_min_confidence: int | None


# ── Regime Adapter ─────────────────────────────────────────────────────────────

class RegimeAdaptation(BaseModel):
    regime: str
    signal: str          # BUY | SELL
    symbol: str | None   # None = applies to all symbols
    timeframe: str | None
    sample_size: int
    win_rate: float
    expectancy: float
    recommendation: Recommendation
    reason: str


class RegimeAdapterResult(BaseModel):
    evaluated_at: datetime
    adaptations: list[RegimeAdaptation]
    regimes_observed: list[str]
    dominant_regime: str | None
    regime_distribution: dict[str, int]   # regime → count
    per_regime_performance: dict[str, dict[str, Any]]


# ── Risk Tuner ────────────────────────────────────────────────────────────────

class RiskTuningResult(BaseModel):
    evaluated_at: datetime
    current_win_rate: float | None
    current_expectancy: float | None
    current_profit_factor: float | None
    max_observed_drawdown_pct: float | None
    suggested_position_size_multiplier: float  # 0.25 - 1.0 - 1.5
    suggested_min_confidence: int              # threshold hint
    risk_level: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
    throttle_recommended: bool
    disable_recommended: bool
    reasoning: list[str]
    policy_hints: dict[str, Any]  # structured hints for PolicyContract generator


# ── Top-level orchestrated report ─────────────────────────────────────────────

class AdaptiveIntelligenceReport(BaseModel):
    generated_at: datetime
    environment: str
    lookback_days: int
    strategy_feedback: StrategyFeedbackResult
    calibration: ConfidenceCalibrationResult
    regime: RegimeAdapterResult
    risk: RiskTuningResult
    # Aggregate advisory signal
    overall_recommendation: Recommendation
    overall_reasoning: str
    policy_hints: dict[str, Any]  # merged hints for downstream consumption

    def to_summary(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "overall_recommendation": self.overall_recommendation,
            "overall_reasoning": self.overall_reasoning,
            "risk_level": self.risk.risk_level,
            "suggested_min_confidence": self.risk.suggested_min_confidence,
            "suggested_position_size_multiplier": self.risk.suggested_position_size_multiplier,
            "well_calibrated": self.calibration.well_calibrated,
            "dominant_regime": self.regime.dominant_regime,
            "policy_hints": self.policy_hints,
        }
