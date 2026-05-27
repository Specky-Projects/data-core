"""Tests for ConfidenceSafetyValidator — BOOST blocking and penalty logic."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.adaptive_intelligence.dto import (
    MIN_SAMPLE_FOR_BOOST,
    AdaptiveIntelligenceReport,
    ConfidenceCalibrationResult,
    RegimeAdapterResult,
    RiskTuningResult,
    StrategyFeedbackResult,
    StrategySlice,
)
from app.adaptive_policy.validator import (
    ConfidenceSafetyValidator,
    REPLAYABILITY_BOOST_THRESHOLD,
    QUANT_BOOST_THRESHOLD,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _slice(
    recommendation: str = "BOOST",
    sample_size: int = MIN_SAMPLE_FOR_BOOST,
    profit_factor: float | None = 2.0,
    win_rate: float = 0.70,
) -> StrategySlice:
    return StrategySlice(
        symbol="BTCUSDT",
        timeframe="1h",
        regime="trending",
        signal="BUY",
        sample_size=sample_size,
        win_rate=win_rate,
        avg_return_pct=1.5,
        expectancy=0.8,
        max_drawdown_pct=2.0,
        profit_factor=profit_factor,
        avg_mfe_pct=2.0,
        avg_mae_pct=0.5,
        recommendation=recommendation,
        recommendation_reason="test",
    )


def _strategy(slices: list | None = None, top_performers: list | None = None) -> StrategyFeedbackResult:
    return StrategyFeedbackResult(
        evaluated_at=_now(),
        lookback_days=30,
        total_outcomes=50,
        slices=slices or [],
        summary={"BOOST": 1, "KEEP": 0, "THROTTLE": 0, "DISABLE": 0, "OBSERVE_ONLY": 0},
        top_performers=top_performers or ["BTCUSDT|1h|trending|BUY"],
        underperformers=[],
    )


def _calibration(
    well_calibrated: bool = True,
    overconfidence: bool = False,
    slope: float | None = 0.01,
    threshold: int | None = 61,
) -> ConfidenceCalibrationResult:
    return ConfidenceCalibrationResult(
        evaluated_at=_now(),
        total_outcomes=50,
        buckets=[],
        calibrated_threshold=threshold,
        overall_calibration_slope=slope,
        well_calibrated=well_calibrated,
        overconfidence_warning=overconfidence,
        underconfidence_warning=False,
        recommended_min_confidence=threshold,
    )


def _regime() -> RegimeAdapterResult:
    return RegimeAdapterResult(
        evaluated_at=_now(),
        adaptations=[],
        regimes_observed=["trending"],
        dominant_regime="trending",
        regime_distribution={"trending": 50},
        per_regime_performance={},
    )


def _risk() -> RiskTuningResult:
    return RiskTuningResult(
        evaluated_at=_now(),
        current_win_rate=0.65,
        current_expectancy=0.5,
        current_profit_factor=2.0,
        max_observed_drawdown_pct=2.0,
        suggested_position_size_multiplier=1.0,
        suggested_min_confidence=55,
        risk_level="LOW",
        throttle_recommended=False,
        disable_recommended=False,
        reasoning=["good performance"],
        policy_hints={},
    )


def _ai_report(
    slices: list | None = None,
    calibration: ConfidenceCalibrationResult | None = None,
    top_performers: list | None = None,
) -> AdaptiveIntelligenceReport:
    _slices = slices if slices is not None else [_slice()]
    _cal = calibration or _calibration()
    _top = top_performers if top_performers is not None else ["BTCUSDT|1h|trending|BUY"]
    return AdaptiveIntelligenceReport(
        generated_at=_now(),
        environment="test",
        lookback_days=30,
        strategy_feedback=_strategy(slices=_slices, top_performers=_top),
        calibration=_cal,
        regime=_regime(),
        risk=_risk(),
        overall_recommendation="BOOST",
        overall_reasoning="test",
        policy_hints={},
    )


def _validate(
    ai_report: AdaptiveIntelligenceReport | None = None,
    replayability: int = 80,
    quant: int = 80,
    safe_mode: bool = False,
):
    report = ai_report or _ai_report()
    v = ConfidenceSafetyValidator()
    return v.validate(
        ai_report=report,
        replayability_score=replayability,
        quant_reliability_score=quant,
        operational_safe_mode=safe_mode,
    )


# ── Tests: BOOST allowed ──────────────────────────────────────────────────────

class TestBoostAllowed:
    def test_good_conditions_boost_allowed(self):
        result = _validate()
        assert result.boost_allowed is True
        assert result.block_reasons == []

    def test_no_confidence_penalty_when_healthy(self):
        result = _validate()
        assert result.confidence_penalty == 0
        assert result.uncertainty_penalty == 0


# ── Tests: BOOST blocked ──────────────────────────────────────────────────────

class TestBoostBlocked:
    def test_low_sample_size_blocks_boost(self):
        slices = [_slice(sample_size=MIN_SAMPLE_FOR_BOOST - 1)]
        result = _validate(ai_report=_ai_report(slices=slices))
        assert result.boost_allowed is False
        assert any("sample_size" in r for r in result.block_reasons)

    def test_undefined_profit_factor_blocks_boost(self):
        slices = [_slice(profit_factor=None)]
        result = _validate(ai_report=_ai_report(slices=slices))
        assert result.boost_allowed is False
        assert any("profit_factor" in r for r in result.block_reasons)

    def test_not_well_calibrated_blocks_boost(self):
        cal = _calibration(well_calibrated=False)
        result = _validate(ai_report=_ai_report(calibration=cal))
        assert result.boost_allowed is False
        assert any("calibrat" in r for r in result.block_reasons)

    def test_overconfidence_blocks_boost(self):
        cal = _calibration(overconfidence=True)
        result = _validate(ai_report=_ai_report(calibration=cal))
        assert result.boost_allowed is False
        assert any("overconfidenc" in r for r in result.block_reasons)

    def test_negative_slope_blocks_boost(self):
        cal = _calibration(slope=-0.01)
        result = _validate(ai_report=_ai_report(calibration=cal))
        assert result.boost_allowed is False
        assert any("slope" in r for r in result.block_reasons)

    def test_low_replayability_blocks_boost(self):
        result = _validate(replayability=REPLAYABILITY_BOOST_THRESHOLD - 1)
        assert result.boost_allowed is False
        assert any("replayability" in r for r in result.block_reasons)

    def test_low_quant_blocks_boost(self):
        result = _validate(quant=QUANT_BOOST_THRESHOLD - 1)
        assert result.boost_allowed is False
        assert any("quant_reliab" in r for r in result.block_reasons)

    def test_operational_safe_mode_blocks_boost(self):
        result = _validate(safe_mode=True)
        assert result.boost_allowed is False
        assert any("safe_mode" in r for r in result.block_reasons)

    def test_multiple_reasons_accumulate(self):
        slices = [_slice(profit_factor=None)]
        cal = _calibration(well_calibrated=False, overconfidence=True)
        result = _validate(ai_report=_ai_report(slices=slices, calibration=cal), safe_mode=True)
        assert result.boost_allowed is False
        assert len(result.block_reasons) >= 3


# ── Tests: Penalties ──────────────────────────────────────────────────────────

class TestPenalties:
    def test_overconfidence_adds_confidence_penalty(self):
        cal = _calibration(overconfidence=True, well_calibrated=False)
        result = _validate(ai_report=_ai_report(calibration=cal))
        assert result.confidence_penalty > 0

    def test_not_calibrated_adds_penalty(self):
        cal = _calibration(well_calibrated=False)
        result = _validate(ai_report=_ai_report(calibration=cal))
        assert result.confidence_penalty >= 10

    def test_negative_slope_adds_penalty(self):
        cal = _calibration(slope=-0.05)
        result = _validate(ai_report=_ai_report(calibration=cal))
        assert result.confidence_penalty >= 10

    def test_low_replayability_adds_penalty(self):
        result = _validate(replayability=50)
        # 50 < 70 baseline → (70-50)//10 * 5 = 10 pts
        assert result.confidence_penalty >= 10

    def test_low_quant_adds_penalty(self):
        result = _validate(quant=50)
        assert result.confidence_penalty >= 10

    def test_undefined_pf_adds_uncertainty_penalty(self):
        slices = [_slice(profit_factor=None)]
        result = _validate(ai_report=_ai_report(slices=slices))
        assert result.uncertainty_penalty >= 5

    def test_no_calibrated_threshold_adds_uncertainty_penalty(self):
        cal = _calibration(threshold=None)
        result = _validate(ai_report=_ai_report(calibration=cal))
        assert result.uncertainty_penalty >= 10

    def test_confidence_penalty_capped(self):
        """Penalty should not exceed _MAX_CONFIDENCE_PENALTY."""
        cal = _calibration(well_calibrated=False, overconfidence=True, slope=-0.1)
        result = _validate(
            ai_report=_ai_report(calibration=cal),
            replayability=30,
            quant=30,
            safe_mode=True,
        )
        assert result.confidence_penalty <= 40

    def test_uncertainty_penalty_capped(self):
        slices = [_slice(profit_factor=None) for _ in range(5)]
        result = _validate(ai_report=_ai_report(slices=slices, top_performers=["a", "b", "c", "d", "e"]))
        assert result.uncertainty_penalty <= 20


# ── Tests: Warnings ───────────────────────────────────────────────────────────

class TestWarnings:
    def test_safe_mode_propagates_warning(self):
        result = _validate(safe_mode=True)
        assert any("safe_mode" in w for w in result.warnings)

    def test_replayability_penalty_emits_warning(self):
        result = _validate(replayability=50)
        assert any("replayability" in w for w in result.warnings)

    def test_no_calibrated_threshold_emits_warning(self):
        cal = _calibration(threshold=None)
        result = _validate(ai_report=_ai_report(calibration=cal))
        assert any("threshold" in w for w in result.warnings)
