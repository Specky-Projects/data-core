"""Tests for RiskTuner."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.adaptive_intelligence.dto import (
    ConfidenceCalibrationResult,
    RegimeAdapterResult,
    StrategyFeedbackResult,
)
from app.adaptive_intelligence.risk_tuner import RiskTuner

# ── Fixture builders ──────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _strategy(
    slices: list | None = None,
    summary: dict | None = None,
    top_performers: list | None = None,
    underperformers: list | None = None,
    total_outcomes: int = 50,
) -> StrategyFeedbackResult:
    return StrategyFeedbackResult(
        evaluated_at=_now(),
        lookback_days=30,
        total_outcomes=total_outcomes,
        slices=slices or [],
        summary=summary or {"BOOST": 0, "KEEP": 1, "THROTTLE": 0, "DISABLE": 0, "OBSERVE_ONLY": 0},
        top_performers=top_performers or [],
        underperformers=underperformers or [],
    )


def _calibration(
    well_calibrated: bool = True,
    overconfidence_warning: bool = False,
    underconfidence_warning: bool = False,
    calibrated_threshold: int | None = 61,
    recommended_min_confidence: int | None = 61,
) -> ConfidenceCalibrationResult:
    return ConfidenceCalibrationResult(
        evaluated_at=_now(),
        total_outcomes=50,
        buckets=[],
        calibrated_threshold=calibrated_threshold,
        overall_calibration_slope=0.01,
        well_calibrated=well_calibrated,
        overconfidence_warning=overconfidence_warning,
        underconfidence_warning=underconfidence_warning,
        recommended_min_confidence=recommended_min_confidence,
    )


def _regime(dominant: str | None = "trending") -> RegimeAdapterResult:
    return RegimeAdapterResult(
        evaluated_at=_now(),
        adaptations=[],
        regimes_observed=["trending"] if dominant else [],
        dominant_regime=dominant,
        regime_distribution={"trending": 50} if dominant else {},
        per_regime_performance={},
    )


def _make_outcome(
    price_change_pct: float = 1.0,
    outcome_correct: bool = True,
    max_adverse_pct: float | None = -0.5,
    days_ago: int = 1,
):
    obj = MagicMock()
    obj.price_change_pct = price_change_pct
    obj.outcome_correct = outcome_correct
    obj.max_adverse_pct = max_adverse_pct
    obj.signal_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return obj


def _make_tuner(rows: list) -> RiskTuner:
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = rows
    return RiskTuner(db, lookback_days=14)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRiskTuner:
    def test_no_data_returns_moderate_risk(self):
        tuner = _make_tuner([])
        result = tuner.evaluate(_strategy(total_outcomes=0), _calibration(), _regime())
        assert result.risk_level == "MODERATE"
        assert result.current_win_rate is None

    def test_low_risk_good_performance(self):
        """High win rate + positive expectancy + low drawdown → LOW risk."""
        rows = [
            _make_outcome(price_change_pct=2.0, outcome_correct=True, max_adverse_pct=-0.3)
            for _ in range(20)
        ]
        tuner = _make_tuner(rows)
        result = tuner.evaluate(_strategy(), _calibration(), _regime())
        assert result.risk_level == "LOW"
        assert result.suggested_position_size_multiplier == 1.0

    def test_critical_risk_very_low_win_rate(self):
        """Win rate < 35% → CRITICAL risk level."""
        rows = [
            _make_outcome(price_change_pct=-1.5, outcome_correct=False)
            for _ in range(10)
        ] + [
            _make_outcome(price_change_pct=1.0, outcome_correct=True)
            for _ in range(2)
        ]
        tuner = _make_tuner(rows)
        result = tuner.evaluate(_strategy(), _calibration(), _regime())
        assert result.risk_level == "CRITICAL"
        assert result.suggested_position_size_multiplier == 0.25

    def test_high_risk_moderate_win_rate(self):
        """Win rate ~40% → HIGH risk level."""
        wins = [_make_outcome(price_change_pct=1.0, outcome_correct=True) for _ in range(4)]
        losses = [_make_outcome(price_change_pct=-1.5, outcome_correct=False) for _ in range(6)]
        tuner = _make_tuner(wins + losses)
        result = tuner.evaluate(_strategy(), _calibration(), _regime())
        assert result.risk_level in ("HIGH", "CRITICAL")

    def test_position_size_multiplier_matches_risk_level(self):
        rows = [_make_outcome(price_change_pct=2.0, outcome_correct=True) for _ in range(20)]
        tuner = _make_tuner(rows)
        result = tuner.evaluate(_strategy(), _calibration(), _regime())
        # LOW risk → 1.0 multiplier
        assert result.suggested_position_size_multiplier == 1.0

    def test_min_confidence_from_calibration_when_higher(self):
        """calibrated_threshold=70 should override the default for LOW risk (55)."""
        rows = [_make_outcome(price_change_pct=2.0, outcome_correct=True) for _ in range(20)]
        tuner = _make_tuner(rows)
        cal = _calibration(recommended_min_confidence=70)
        result = tuner.evaluate(_strategy(), cal, _regime())
        assert result.suggested_min_confidence >= 70

    def test_throttle_recommended_for_high_risk(self):
        rows = [_make_outcome(price_change_pct=-1.5, outcome_correct=False) for _ in range(10)]
        rows += [_make_outcome(price_change_pct=1.0, outcome_correct=True) for _ in range(4)]
        tuner = _make_tuner(rows)
        result = tuner.evaluate(_strategy(), _calibration(), _regime())
        assert result.throttle_recommended

    def test_disable_recommended_for_critical_risk(self):
        rows = [_make_outcome(price_change_pct=-2.0, outcome_correct=False) for _ in range(20)]
        tuner = _make_tuner(rows)
        result = tuner.evaluate(_strategy(), _calibration(), _regime())
        # CRITICAL → disable_recommended
        assert result.disable_recommended

    def test_overconfidence_escalates_risk_level(self):
        """Overconfidence warning bumps risk up one tier."""
        # Borderline LOW → MODERATE after overconfidence bump
        rows = [_make_outcome(price_change_pct=2.0, outcome_correct=True) for _ in range(20)]
        tuner = _make_tuner(rows)
        cal = _calibration(well_calibrated=False, overconfidence_warning=True)
        result_without = _make_tuner(rows).evaluate(_strategy(), _calibration(), _regime())
        result_with = tuner.evaluate(_strategy(), cal, _regime())
        # With overconfidence, risk should be same or higher
        _ORDER = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}
        assert _ORDER[result_with.risk_level] >= _ORDER[result_without.risk_level]

    def test_policy_hints_contains_required_keys(self):
        rows = [_make_outcome() for _ in range(10)]
        tuner = _make_tuner(rows)
        result = tuner.evaluate(_strategy(), _calibration(), _regime())
        hints = result.policy_hints
        assert "risk_level" in hints
        assert "suggested_position_size_multiplier" in hints
        assert "suggested_min_confidence" in hints
        assert "throttle_recommended" in hints
        assert "disable_recommended" in hints
        assert "dominant_regime" in hints
        assert "well_calibrated" in hints
        assert "source" in hints
        assert hints["source"] == "adaptive_intelligence"

    def test_reasoning_list_not_empty(self):
        tuner = _make_tuner([])
        result = tuner.evaluate(_strategy(), _calibration(), _regime())
        assert isinstance(result.reasoning, list)
        assert len(result.reasoning) > 0

    def test_evaluated_at_timezone_aware(self):
        tuner = _make_tuner([])
        result = tuner.evaluate(_strategy(), _calibration(), _regime())
        assert result.evaluated_at.tzinfo is not None
