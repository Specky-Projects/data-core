"""Tests for AdaptiveIntelligenceOrchestrator — engine composition and fallbacks."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.adaptive_intelligence.dto import (
    AdaptiveIntelligenceReport,
    ConfidenceCalibrationResult,
    RegimeAdapterResult,
    RiskTuningResult,
    StrategyFeedbackResult,
)
from app.adaptive_intelligence.orchestrator import (
    AdaptiveIntelligenceOrchestrator,
    _derive_overall,
    _empty_calibration,
    _empty_regime,
    _empty_risk,
    _empty_strategy,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _strategy(
    total: int = 0,
    top: list | None = None,
    underperf: list | None = None,
    summary: dict | None = None,
) -> StrategyFeedbackResult:
    return StrategyFeedbackResult(
        evaluated_at=_now(),
        lookback_days=30,
        total_outcomes=total,
        slices=[],
        summary=summary or {"BOOST": 0, "KEEP": 0, "THROTTLE": 0, "DISABLE": 0, "OBSERVE_ONLY": 0},
        top_performers=top or [],
        underperformers=underperf or [],
    )


def _calibration(
    well_calibrated: bool = True,
    overconfidence: bool = False,
) -> ConfidenceCalibrationResult:
    return ConfidenceCalibrationResult(
        evaluated_at=_now(),
        total_outcomes=20,
        buckets=[],
        calibrated_threshold=61,
        overall_calibration_slope=0.01,
        well_calibrated=well_calibrated,
        overconfidence_warning=overconfidence,
        underconfidence_warning=False,
        recommended_min_confidence=61,
    )


def _regime(dominant: str | None = "trending") -> RegimeAdapterResult:
    return RegimeAdapterResult(
        evaluated_at=_now(),
        adaptations=[],
        regimes_observed=[],
        dominant_regime=dominant,
        regime_distribution={},
        per_regime_performance={},
    )


def _risk(level: str = "LOW", throttle: bool = False, disable: bool = False) -> RiskTuningResult:
    return RiskTuningResult(
        evaluated_at=_now(),
        current_win_rate=0.6,
        current_expectancy=0.1,
        current_profit_factor=1.8,
        max_observed_drawdown_pct=2.0,
        suggested_position_size_multiplier=1.0,
        suggested_min_confidence=55,
        risk_level=level,  # type: ignore[arg-type]
        throttle_recommended=throttle,
        disable_recommended=disable,
        reasoning=["test"],
        policy_hints={"source": "adaptive_intelligence", "risk_level": level},
    )


# ── _derive_overall tests ─────────────────────────────────────────────────────

class TestDeriveOverall:
    def test_observe_only_when_no_outcomes(self):
        rec, _ = _derive_overall(_strategy(total=0), _calibration(), _risk())
        assert rec == "OBSERVE_ONLY"

    def test_boost_when_low_risk_top_performers_calibrated(self):
        strat = _strategy(total=50, top=["BTCUSDT|1h|trending|BUY"])
        rec, _ = _derive_overall(strat, _calibration(well_calibrated=True), _risk("LOW"))
        assert rec == "BOOST"

    def test_no_boost_when_not_well_calibrated(self):
        strat = _strategy(total=50, top=["BTCUSDT|1h|trending|BUY"])
        rec, _ = _derive_overall(strat, _calibration(well_calibrated=False), _risk("LOW"))
        assert rec != "BOOST"

    def test_no_boost_when_overconfidence_warning(self):
        strat = _strategy(total=50, top=["BTCUSDT|1h|trending|BUY"])
        rec, _ = _derive_overall(strat, _calibration(overconfidence=True), _risk("LOW"))
        assert rec != "BOOST"

    def test_disable_when_critical_risk(self):
        rec, _ = _derive_overall(_strategy(total=50), _calibration(), _risk("CRITICAL"))
        assert rec == "DISABLE"

    def test_throttle_when_high_risk(self):
        rec, _ = _derive_overall(_strategy(total=50), _calibration(), _risk("HIGH"))
        assert rec == "THROTTLE"

    def test_keep_when_moderate_risk_no_flags(self):
        rec, _ = _derive_overall(_strategy(total=50), _calibration(), _risk("MODERATE"))
        assert rec == "KEEP"

    def test_disable_when_majority_underperformers(self):
        strat = _strategy(
            total=50,
            underperf=["a", "b", "c"],
            summary={
                "DISABLE": 3,
                "KEEP": 0,
                "THROTTLE": 0,
                "BOOST": 0,
                "OBSERVE_ONLY": 0,
            },
        )
        # risk_level=LOW but disable_recommended=True → DISABLE
        rec, _ = _derive_overall(strat, _calibration(), _risk("LOW", disable=True))
        assert rec == "DISABLE"


# ── Empty fallback builders ────────────────────────────────────────────────────

class TestEmptyFallbacks:
    def test_empty_strategy_is_valid(self):
        s = _empty_strategy(30)
        assert s.total_outcomes == 0
        assert s.lookback_days == 30

    def test_empty_calibration_is_valid(self):
        c = _empty_calibration()
        assert not c.well_calibrated
        assert c.total_outcomes == 0

    def test_empty_regime_is_valid(self):
        r = _empty_regime()
        assert r.dominant_regime is None

    def test_empty_risk_is_valid(self):
        r = _empty_risk()
        assert r.risk_level == "MODERATE"
        assert r.suggested_position_size_multiplier == 1.0


# ── Orchestrator end-to-end ────────────────────────────────────────────────────

class TestOrchestrator:
    def _make_orch(self, rows: list | None = None) -> AdaptiveIntelligenceOrchestrator:
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = rows or []
        return AdaptiveIntelligenceOrchestrator(db, lookback_days=30, environment="test")

    def test_evaluate_returns_report_type(self):
        orch = self._make_orch()
        result = orch.evaluate()
        assert isinstance(result, AdaptiveIntelligenceReport)

    def test_evaluate_with_empty_db(self):
        orch = self._make_orch([])
        result = orch.evaluate()
        assert result.overall_recommendation == "OBSERVE_ONLY"
        assert result.strategy_feedback.total_outcomes == 0

    def test_report_fields_present(self):
        orch = self._make_orch()
        result = orch.evaluate()
        assert result.generated_at is not None
        assert result.environment == "test"
        assert result.lookback_days == 30
        assert result.overall_recommendation is not None
        assert isinstance(result.overall_reasoning, str)
        assert isinstance(result.policy_hints, dict)

    def test_to_summary_returns_dict(self):
        orch = self._make_orch()
        result = orch.evaluate()
        summary = result.to_summary()
        assert "overall_recommendation" in summary
        assert "risk_level" in summary
        assert "suggested_min_confidence" in summary
        assert "suggested_position_size_multiplier" in summary
        assert "well_calibrated" in summary
        assert "dominant_regime" in summary
        assert "policy_hints" in summary
        assert "generated_at" in summary

    def test_engine_failure_does_not_propagate(self):
        """If one engine fails, the orchestrator recovers with a safe fallback."""
        db = MagicMock()
        # Simulate strategy engine raising an exception
        db.query.side_effect = RuntimeError("database error")
        orch = AdaptiveIntelligenceOrchestrator(db, lookback_days=30, environment="test")
        result = orch.evaluate()
        # Should not raise; fallback empty results returned
        assert isinstance(result, AdaptiveIntelligenceReport)
        assert result.strategy_feedback.total_outcomes == 0

    def test_policy_hints_includes_source(self):
        orch = self._make_orch()
        result = orch.evaluate()
        # policy_hints comes from risk.policy_hints merged with orchestrator additions
        # The empty risk fallback sets an empty dict, but orchestrator enriches it
        assert "overall_recommendation" in result.policy_hints
        assert "dominant_regime" in result.policy_hints

    def test_generated_at_is_timezone_aware(self):
        orch = self._make_orch()
        result = orch.evaluate()
        assert result.generated_at.tzinfo is not None
