"""Tests for adaptive intelligence DTOs and _classify_recommendation logic."""

from __future__ import annotations

import pytest

from app.adaptive_intelligence.dto import (
    MIN_SAMPLE_FOR_BOOST,
    MIN_SAMPLE_FOR_DISABLE,
    MIN_SAMPLE_FOR_RECOMMENDATION,
    _classify_recommendation,
)


class TestClassifyRecommendation:
    def test_observe_only_when_sample_too_small(self):
        assert _classify_recommendation(0.70, 0.5, 2.0, MIN_SAMPLE_FOR_RECOMMENDATION - 1) == "OBSERVE_ONLY"

    def test_observe_only_at_zero_sample(self):
        assert _classify_recommendation(0.80, 1.0, 3.0, 0) == "OBSERVE_ONLY"

    def test_boost_all_criteria_met(self):
        rec = _classify_recommendation(
            win_rate=0.65,
            expectancy=0.10,
            profit_factor=2.0,
            sample_size=MIN_SAMPLE_FOR_BOOST,
        )
        assert rec == "BOOST"

    def test_boost_requires_min_sample_30(self):
        """BOOST must not trigger with fewer than MIN_SAMPLE_FOR_BOOST samples."""
        rec = _classify_recommendation(
            win_rate=0.65,
            expectancy=0.10,
            profit_factor=2.0,
            sample_size=MIN_SAMPLE_FOR_BOOST - 1,
        )
        # With good win rate and expectancy, should be KEEP not BOOST
        assert rec == "KEEP"

    def test_boost_requires_profit_factor_1_5(self):
        rec = _classify_recommendation(
            win_rate=0.65,
            expectancy=0.10,
            profit_factor=1.4,  # just below threshold
            sample_size=MIN_SAMPLE_FOR_BOOST,
        )
        assert rec != "BOOST"

    def test_boost_requires_positive_expectancy(self):
        rec = _classify_recommendation(
            win_rate=0.65,
            expectancy=-0.01,  # negative
            profit_factor=2.0,
            sample_size=MIN_SAMPLE_FOR_BOOST,
        )
        assert rec != "BOOST"

    def test_boost_requires_win_rate_60(self):
        rec = _classify_recommendation(
            win_rate=0.59,  # just below threshold
            expectancy=0.10,
            profit_factor=2.0,
            sample_size=MIN_SAMPLE_FOR_BOOST,
        )
        assert rec != "BOOST"

    def test_keep_acceptable_performance(self):
        rec = _classify_recommendation(
            win_rate=0.52,
            expectancy=0.05,
            profit_factor=1.2,
            sample_size=MIN_SAMPLE_FOR_RECOMMENDATION,
        )
        assert rec == "KEEP"

    def test_keep_at_boundary_50pct(self):
        rec = _classify_recommendation(
            win_rate=0.50,
            expectancy=0.0,
            profit_factor=None,
            sample_size=MIN_SAMPLE_FOR_RECOMMENDATION,
        )
        assert rec == "KEEP"

    def test_disable_requires_min_sample_20(self):
        """DISABLE must not trigger with fewer than MIN_SAMPLE_FOR_DISABLE samples."""
        rec = _classify_recommendation(
            win_rate=0.30,
            expectancy=-0.20,
            profit_factor=0.5,
            sample_size=MIN_SAMPLE_FOR_DISABLE - 1,
        )
        # Should be THROTTLE because sample too small for DISABLE
        assert rec == "THROTTLE"

    def test_disable_poor_performance_adequate_sample(self):
        rec = _classify_recommendation(
            win_rate=0.30,
            expectancy=-0.20,
            profit_factor=0.5,
            sample_size=MIN_SAMPLE_FOR_DISABLE,
        )
        assert rec == "DISABLE"

    def test_disable_requires_win_rate_below_40(self):
        rec = _classify_recommendation(
            win_rate=0.41,  # above threshold
            expectancy=-0.20,
            profit_factor=0.5,
            sample_size=MIN_SAMPLE_FOR_DISABLE,
        )
        assert rec != "DISABLE"

    def test_throttle_marginal_performance(self):
        rec = _classify_recommendation(
            win_rate=0.45,
            expectancy=-0.05,  # negative expectancy, win rate < 50%
            profit_factor=0.9,
            sample_size=MIN_SAMPLE_FOR_RECOMMENDATION,
        )
        assert rec == "THROTTLE"

    def test_none_profit_factor_treated_as_zero(self):
        """None profit_factor (no losses) should not prevent KEEP classification."""
        rec = _classify_recommendation(
            win_rate=0.55,
            expectancy=0.10,
            profit_factor=None,
            sample_size=MIN_SAMPLE_FOR_RECOMMENDATION,
        )
        assert rec == "KEEP"

    def test_none_profit_factor_prevents_boost(self):
        """None profit_factor treated as 0.0 → pf < 1.5 → not BOOST."""
        rec = _classify_recommendation(
            win_rate=0.65,
            expectancy=0.10,
            profit_factor=None,  # treated as 0.0
            sample_size=MIN_SAMPLE_FOR_BOOST,
        )
        # profit_factor=None → 0.0 < 1.5 → BOOST threshold not met → KEEP
        assert rec == "KEEP"

    def test_exactly_at_disable_boundaries(self):
        """Exact boundary: win_rate=0.40 should NOT trigger DISABLE (needs < 0.40)."""
        rec = _classify_recommendation(
            win_rate=0.40,
            expectancy=-0.15,
            profit_factor=0.5,
            sample_size=MIN_SAMPLE_FOR_DISABLE,
        )
        assert rec != "DISABLE"

    def test_throttle_fallback_default(self):
        """When no other rule matches, THROTTLE is the default."""
        rec = _classify_recommendation(
            win_rate=0.48,
            expectancy=-0.01,
            profit_factor=0.98,
            sample_size=MIN_SAMPLE_FOR_RECOMMENDATION,
        )
        assert rec == "THROTTLE"
