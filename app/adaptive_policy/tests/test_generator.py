"""Tests for AdaptivePolicyGenerator — full contract generation."""

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
from app.adaptive_policy.generator import AdaptivePolicyGenerator, _safe_fallback
from app.adaptive_policy.dto import AdaptivePolicyContract


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _slice(
    recommendation: str = "KEEP",
    sample_size: int = MIN_SAMPLE_FOR_BOOST,
    profit_factor: float | None = 1.8,
) -> StrategySlice:
    return StrategySlice(
        symbol="BTCUSDT", timeframe="1h", regime="trending", signal="BUY",
        sample_size=sample_size, win_rate=0.62, avg_return_pct=1.5, expectancy=0.5,
        max_drawdown_pct=2.0, profit_factor=profit_factor,
        avg_mfe_pct=2.0, avg_mae_pct=0.5,
        recommendation=recommendation, recommendation_reason="test",
    )


def _strategy(
    slices: list | None = None,
    top_performers: list | None = None,
    total_outcomes: int = 50,
) -> StrategyFeedbackResult:
    return StrategyFeedbackResult(
        evaluated_at=_now(), lookback_days=30, total_outcomes=total_outcomes,
        slices=slices or [], summary={"BOOST": 0, "KEEP": 1, "THROTTLE": 0, "DISABLE": 0, "OBSERVE_ONLY": 0},
        top_performers=top_performers or [], underperformers=[],
    )


def _calibration(
    well_calibrated: bool = True,
    overconfidence: bool = False,
    slope: float = 0.01,
    threshold: int | None = 61,
) -> ConfidenceCalibrationResult:
    return ConfidenceCalibrationResult(
        evaluated_at=_now(), total_outcomes=50, buckets=[],
        calibrated_threshold=threshold, overall_calibration_slope=slope,
        well_calibrated=well_calibrated, overconfidence_warning=overconfidence,
        underconfidence_warning=False, recommended_min_confidence=threshold,
    )


def _regime() -> RegimeAdapterResult:
    return RegimeAdapterResult(
        evaluated_at=_now(), adaptations=[], regimes_observed=["trending"],
        dominant_regime="trending", regime_distribution={"trending": 50}, per_regime_performance={},
    )


def _risk(level: str = "LOW") -> RiskTuningResult:
    size = {"LOW": 1.0, "MODERATE": 0.75, "HIGH": 0.50, "CRITICAL": 0.25}.get(level, 1.0)
    return RiskTuningResult(
        evaluated_at=_now(), current_win_rate=0.60, current_expectancy=0.3,
        current_profit_factor=1.8, max_observed_drawdown_pct=2.0,
        suggested_position_size_multiplier=size, suggested_min_confidence=55,
        risk_level=level, throttle_recommended=level in ("HIGH", "CRITICAL"),
        disable_recommended=level == "CRITICAL",
        reasoning=[f"test risk {level}"], policy_hints={},
    )


def _ai_report(
    risk_level: str = "LOW",
    calibration: ConfidenceCalibrationResult | None = None,
    slices: list | None = None,
    top_performers: list | None = None,
    total_outcomes: int = 50,
) -> AdaptiveIntelligenceReport:
    cal = calibration or _calibration()
    overall_rec = "BOOST" if risk_level == "LOW" and top_performers else "KEEP"
    return AdaptiveIntelligenceReport(
        generated_at=_now(), environment="test", lookback_days=30,
        strategy_feedback=_strategy(slices=slices, top_performers=top_performers, total_outcomes=total_outcomes),
        calibration=cal, regime=_regime(), risk=_risk(risk_level),
        overall_recommendation=overall_rec, overall_reasoning="test",
        policy_hints={},
    )


def _truth_report(
    score: int = 85,
    safe_mode: bool = False,
    status: str = "HEALTHY",
) -> MagicMock:
    r = MagicMock()
    r.operational_confidence_score = score
    r.replayability_score = score
    r.quant_reliability_score = score
    r.safe_mode = safe_mode
    r.operational_status = status
    return r


def _gen(rollout_phase: int = 1) -> AdaptivePolicyGenerator:
    return AdaptivePolicyGenerator(rollout_phase=rollout_phase, environment="test")


# ── Tests: basic contract shape ───────────────────────────────────────────────

class TestContractShape:
    def test_returns_contract_type(self):
        contract = _gen().generate(_ai_report())
        assert isinstance(contract, AdaptivePolicyContract)

    def test_contract_has_all_required_fields(self):
        c = _gen().generate(_ai_report())
        assert c.version
        assert c.generated_at
        assert c.expires_at
        assert c.environment == "test"
        assert c.mode in ["OBSERVE_ONLY", "WARN_ONLY", "SAFE_MODE", "FAIL_CLOSED"]
        assert c.status in ["OK", "WARNING", "CRITICAL"]
        assert c.risk_level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert isinstance(c.policy_hints, list)
        assert isinstance(c.allowed_actions, list)
        assert isinstance(c.blocked_actions, list)
        assert isinstance(c.warnings, list)
        assert isinstance(c.reasons, list)

    def test_kill_switch_always_false(self):
        c = _gen(4).generate(_ai_report("CRITICAL"))
        assert c.kill_switch is False

    def test_position_close_always_allowed(self):
        c = _gen(4).generate(_ai_report("CRITICAL"))
        assert "position_close" in c.allowed_actions

    def test_not_expired_on_creation(self):
        c = _gen().generate(_ai_report())
        assert not c.is_expired()


# ── Tests: mode derivation ────────────────────────────────────────────────────

class TestModeDerivedFromRisk:
    def test_low_risk_phase1_observe_only(self):
        c = _gen(1).generate(_ai_report("LOW"))
        assert c.mode == "OBSERVE_ONLY"

    def test_critical_risk_phase1_still_observe_only(self):
        """Phase 1 always caps at OBSERVE_ONLY regardless of risk."""
        c = _gen(1).generate(_ai_report("CRITICAL"))
        assert c.mode == "OBSERVE_ONLY"

    def test_high_risk_phase3_safe_mode(self):
        c = _gen(3).generate(_ai_report("HIGH"))
        assert c.mode == "SAFE_MODE"

    def test_critical_risk_phase4_fail_closed(self):
        c = _gen(4).generate(_ai_report("CRITICAL"))
        assert c.mode == "FAIL_CLOSED"
        assert c.fail_closed is True

    def test_high_risk_phase4_capped_at_safe_mode(self):
        c = _gen(4).generate(_ai_report("HIGH"))
        assert c.mode == "SAFE_MODE"
        assert c.fail_closed is False

    def test_moderate_risk_phase2_warn_only(self):
        c = _gen(2).generate(_ai_report("MODERATE"))
        assert c.mode == "WARN_ONLY"


# ── Tests: operational truth integration ─────────────────────────────────────

class TestTruthReportIntegration:
    def test_degraded_truth_escalates_mode_in_phase2(self):
        """DEGRADED truth → WARN_ONLY; LOW risk → OBSERVE_ONLY; worst wins → WARN_ONLY."""
        truth = _truth_report(score=65, status="DEGRADED")
        c = _gen(2).generate(_ai_report("LOW"), truth_report=truth)
        assert c.mode == "WARN_ONLY"

    def test_partially_unsafe_truth_escalates_to_safe_mode_in_phase3(self):
        truth = _truth_report(score=55, status="PARTIALLY_UNSAFE")
        c = _gen(3).generate(_ai_report("LOW"), truth_report=truth)
        assert c.mode == "SAFE_MODE"

    def test_no_truth_report_degrades_gracefully(self):
        c = _gen(1).generate(_ai_report("LOW"), truth_report=None)
        assert isinstance(c, AdaptivePolicyContract)
        assert c.mode == "OBSERVE_ONLY"  # phase 1 gate + no truth

    def test_truth_safe_mode_propagates_to_boost_block(self):
        truth = _truth_report(safe_mode=True)
        slices = [_slice(recommendation="BOOST")]
        c = _gen(3).generate(
            _ai_report("LOW", slices=slices, top_performers=["BTCUSDT|1h|trending|BUY"]),
            truth_report=truth,
        )
        assert c.boost_blocked is True

    def test_confidence_penalty_lowers_score(self):
        """Truth with good score + overconfidence warning → score lowered."""
        truth = _truth_report(score=85)
        cal = _calibration(overconfidence=True, well_calibrated=False)
        c = _gen(2).generate(_ai_report("LOW", calibration=cal), truth_report=truth)
        assert c.confidence_score < 85  # penalty applied


# ── Tests: BOOST blocking propagation ────────────────────────────────────────

class TestBoostBlocking:
    def test_boost_blocked_sets_flag(self):
        cal = _calibration(well_calibrated=False)
        slices = [_slice(recommendation="BOOST")]
        c = _gen().generate(
            _ai_report("LOW", calibration=cal, slices=slices, top_performers=["x"])
        )
        assert c.boost_blocked is True
        assert len(c.boost_block_reasons) >= 1

    def test_boost_not_blocked_good_conditions(self):
        """BOOST allowed when: well-calibrated + good truth scores + valid BOOST slice."""
        slices = [_slice(recommendation="BOOST")]
        # Must pass a truth report with good scores; without one, conservative
        # defaults (replayability=50, quant=50) would block BOOST automatically.
        truth = _truth_report(score=90, safe_mode=False, status="HEALTHY")
        c = _gen().generate(
            _ai_report("LOW", slices=slices, top_performers=["BTCUSDT|1h|trending|BUY"]),
            truth_report=truth,
        )
        assert c.boost_blocked is False

    def test_enforcement_hints_disable_boost_when_blocked(self):
        cal = _calibration(well_calibrated=False)
        c = _gen().generate(_ai_report("LOW", calibration=cal))
        assert c.enforcement_hints.disable_boost is True

    def test_enforcement_hints_disable_boost_when_safe_mode(self):
        c = _gen(3).generate(_ai_report("HIGH"))
        assert c.enforcement_hints.disable_boost is True

    def test_enforcement_hints_reduce_position_size_in_safe_mode(self):
        c = _gen(3).generate(_ai_report("HIGH"))
        assert c.enforcement_hints.reduce_position_size is True

    def test_enforcement_hints_disable_live_execution_fail_closed(self):
        c = _gen(4).generate(_ai_report("CRITICAL"))
        assert c.enforcement_hints.disable_live_execution is True


# ── Tests: safe_mode + fail_closed flags ─────────────────────────────────────

class TestSafetyFlags:
    def test_safe_mode_true_in_safe_mode(self):
        c = _gen(3).generate(_ai_report("HIGH"))
        assert c.safe_mode is True

    def test_safe_mode_true_in_fail_closed(self):
        c = _gen(4).generate(_ai_report("CRITICAL"))
        assert c.safe_mode is True
        assert c.fail_closed is True

    def test_safe_mode_false_observe_only(self):
        c = _gen(1).generate(_ai_report("LOW"))
        assert c.safe_mode is False
        assert c.fail_closed is False

    def test_fail_closed_blocks_position_open(self):
        c = _gen(4).generate(_ai_report("CRITICAL"))
        assert "position_open" in c.blocked_actions

    def test_observe_only_no_blocked_actions(self):
        c = _gen(1).generate(_ai_report("LOW"))
        assert c.blocked_actions == []


# ── Tests: fallback ───────────────────────────────────────────────────────────

class TestFallback:
    def test_safe_fallback_is_valid_contract(self):
        c = _safe_fallback("test", 1, "test error")
        assert isinstance(c, AdaptivePolicyContract)
        assert c.mode == "OBSERVE_ONLY"
        assert c.boost_blocked is True
        assert c.status == "WARNING"

    def test_generator_exception_returns_fallback(self):
        """If AI report is malformed, generator returns safe fallback."""
        gen = AdaptivePolicyGenerator(rollout_phase=1, environment="test")
        # Pass something that will fail validation inside generator
        result = gen.generate(ai_report=None)  # type: ignore[arg-type]
        assert isinstance(result, AdaptivePolicyContract)
        assert result.mode == "OBSERVE_ONLY"

    def test_rollout_phase_recorded_in_contract(self):
        c = _gen(3).generate(_ai_report("LOW"))
        assert c.rollout_phase == 3


# ── Tests: no-data fallback ───────────────────────────────────────────────────

class TestNoDataScenario:
    def test_zero_outcomes_produce_observe_only(self):
        """When total_outcomes=0, AI returns OBSERVE_ONLY → contract OBSERVE_ONLY."""
        c = _gen(4).generate(_ai_report("LOW", total_outcomes=0))
        # Phase 4 would normally allow FAIL_CLOSED for CRITICAL, but LOW risk + no data → OK
        assert c.mode in ["OBSERVE_ONLY", "WARN_ONLY"]
