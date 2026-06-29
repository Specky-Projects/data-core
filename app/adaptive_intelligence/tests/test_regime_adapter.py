"""Tests for RegimeAdapter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.adaptive_intelligence.regime_adapter import RegimeAdapter

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_outcome(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    signal: str = "BUY",
    regime: str = "trending",
    price_change_pct: float = 1.0,
    outcome_correct: bool = True,
):
    obj = MagicMock()
    obj.symbol = symbol
    obj.timeframe = timeframe
    obj.signal = signal
    obj.regime = regime
    obj.price_change_pct = price_change_pct
    obj.outcome_correct = outcome_correct
    obj.signal_at = datetime.now(timezone.utc) - timedelta(days=1)
    return obj


def _make_engine(rows: list) -> RegimeAdapter:
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = rows
    return RegimeAdapter(db, lookback_days=30)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRegimeAdapter:
    def test_empty_db_returns_empty_result(self):
        engine = _make_engine([])
        result = engine.evaluate()
        assert result.adaptations == []
        assert result.regimes_observed == []
        assert result.dominant_regime is None
        assert result.regime_distribution == {}

    def test_single_regime_dominant(self):
        rows = [_make_outcome(regime="trending") for _ in range(5)]
        engine = _make_engine(rows)
        result = engine.evaluate()
        assert result.dominant_regime == "trending"
        assert "trending" in result.regimes_observed

    def test_two_regimes_dominant_is_most_frequent(self):
        trending = [_make_outcome(regime="trending") for _ in range(10)]
        ranging = [_make_outcome(regime="ranging") for _ in range(3)]
        engine = _make_engine(trending + ranging)
        result = engine.evaluate()
        assert result.dominant_regime == "trending"
        assert result.regime_distribution["trending"] == 10
        assert result.regime_distribution["ranging"] == 3

    def test_per_regime_performance_computed(self):
        rows = [
            _make_outcome(regime="trending", price_change_pct=1.0, outcome_correct=True)
            for _ in range(5)
        ]
        engine = _make_engine(rows)
        result = engine.evaluate()
        assert "trending" in result.per_regime_performance
        perf = result.per_regime_performance["trending"]
        assert perf["sample_size"] == 5
        assert perf["win_rate"] == pytest.approx(1.0)

    def test_adaptations_separate_per_signal(self):
        """BUY and SELL signals in same regime create separate adaptation entries."""
        buy_rows = [_make_outcome(signal="BUY", regime="trending") for _ in range(3)]
        sell_rows = [_make_outcome(signal="SELL", regime="trending") for _ in range(3)]
        engine = _make_engine(buy_rows + sell_rows)
        result = engine.evaluate()
        signals = {a.signal for a in result.adaptations}
        assert "BUY" in signals
        assert "SELL" in signals

    def test_adaptations_separate_per_symbol(self):
        btc = [_make_outcome(symbol="BTCUSDT", regime="trending") for _ in range(3)]
        eth = [_make_outcome(symbol="ETHUSDT", regime="trending") for _ in range(3)]
        engine = _make_engine(btc + eth)
        result = engine.evaluate()
        symbols = {a.symbol for a in result.adaptations}
        assert "BTCUSDT" in symbols
        assert "ETHUSDT" in symbols

    def test_adaptation_recommendation_observe_only_for_small_sample(self):
        rows = [_make_outcome(regime="trending") for _ in range(5)]
        engine = _make_engine(rows)
        result = engine.evaluate()
        assert result.adaptations[0].recommendation == "OBSERVE_ONLY"

    def test_adaptation_recommendation_boost_for_good_performance(self):
        """30 outcomes with high win rate + PF>=1.5 → BOOST.

        Include a few losses so profit_factor is defined (None is treated as 0).
        25 wins at +2.0 pct, 5 losses at -0.3 pct → PF≈33, wr=83%.
        """
        win_rows = [
            _make_outcome(regime="trending", price_change_pct=2.0, outcome_correct=True)
            for _ in range(25)
        ]
        loss_rows = [
            _make_outcome(regime="trending", price_change_pct=-0.3, outcome_correct=False)
            for _ in range(5)
        ]
        engine = _make_engine(win_rows + loss_rows)
        result = engine.evaluate()
        assert result.adaptations[0].recommendation == "BOOST"

    def test_regimes_observed_sorted(self):
        rows = (
            [_make_outcome(regime="z_regime")] * 2 +
            [_make_outcome(regime="a_regime")] * 2
        )
        engine = _make_engine(rows)
        result = engine.evaluate()
        assert result.regimes_observed == sorted(result.regimes_observed)

    def test_reason_contains_regime_and_signal(self):
        rows = [_make_outcome(regime="ranging", signal="SELL") for _ in range(3)]
        engine = _make_engine(rows)
        result = engine.evaluate()
        assert "ranging" in result.adaptations[0].reason
        assert "SELL" in result.adaptations[0].reason

    def test_evaluated_at_is_timezone_aware(self):
        engine = _make_engine([])
        result = engine.evaluate()
        assert result.evaluated_at.tzinfo is not None
