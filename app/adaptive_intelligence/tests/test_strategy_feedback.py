"""Tests for StrategyFeedbackEngine."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.adaptive_intelligence.strategy_feedback import (
    StrategyFeedbackEngine,
    _Acc,
    _slice_key,
)
from app.adaptive_intelligence.dto import StrategyFeedbackResult


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_outcome(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    signal: str = "BUY",
    regime: str | None = "trending",
    price_change_pct: float = 1.5,
    max_adverse_pct: float = -0.5,
    max_favorable_pct: float = 2.0,
    outcome_correct: bool = True,
    days_ago: int = 1,
):
    """Return a mock TradingSignalOutcome row."""
    obj = MagicMock()
    obj.symbol = symbol
    obj.timeframe = timeframe
    obj.signal = signal
    obj.regime = regime
    obj.price_change_pct = price_change_pct
    obj.max_adverse_pct = max_adverse_pct
    obj.max_favorable_pct = max_favorable_pct
    obj.outcome_correct = outcome_correct
    obj.signal_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return obj


def _make_engine_with_rows(rows: list) -> StrategyFeedbackEngine:
    """Create an engine whose DB query returns the given rows."""
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = rows
    return StrategyFeedbackEngine(db, lookback_days=30)


# ── Accumulator unit tests ─────────────────────────────────────────────────────

class TestAcc:
    def test_empty_accumulator(self):
        acc = _Acc()
        assert acc.sample_size == 0
        assert acc.win_rate == 0.0
        assert acc.expectancy == 0.0
        assert acc.max_drawdown_pct == 0.0
        assert acc.profit_factor is None
        assert acc.avg_mfe_pct is None
        assert acc.avg_mae_pct is None

    def test_add_winning_outcome(self):
        acc = _Acc()
        row = _make_outcome(price_change_pct=2.0, max_adverse_pct=-0.3, max_favorable_pct=2.5)
        acc.add(row)
        assert acc.wins == 1
        assert acc.losses == 0
        assert acc.win_rate == 1.0
        assert acc.gross_profit == 2.0

    def test_add_losing_outcome(self):
        acc = _Acc()
        row = _make_outcome(price_change_pct=-1.0, max_adverse_pct=-1.5, max_favorable_pct=0.2)
        acc.add(row)
        assert acc.wins == 0
        assert acc.losses == 1
        assert acc.win_rate == 0.0
        assert acc.gross_loss == 1.0

    def test_profit_factor_none_when_no_losses(self):
        acc = _Acc()
        acc.add(_make_outcome(price_change_pct=1.0))
        acc.add(_make_outcome(price_change_pct=2.0))
        assert acc.profit_factor is None  # no losses

    def test_profit_factor_computed(self):
        acc = _Acc()
        acc.add(_make_outcome(price_change_pct=2.0))
        acc.add(_make_outcome(price_change_pct=-1.0))
        assert acc.profit_factor == pytest.approx(2.0)

    def test_max_drawdown_is_worst_adverse(self):
        acc = _Acc()
        acc.add(_make_outcome(max_adverse_pct=-0.5))
        acc.add(_make_outcome(max_adverse_pct=-2.0))
        acc.add(_make_outcome(max_adverse_pct=-0.1))
        assert acc.max_drawdown_pct == pytest.approx(2.0)

    def test_expectancy_correct(self):
        """6 wins at +2.0 pct, 4 losses at -1.0 pct → expectancy = 0.6*2 - 0.4*1 = 0.8."""
        acc = _Acc()
        for _ in range(6):
            acc.add(_make_outcome(price_change_pct=2.0))
        for _ in range(4):
            acc.add(_make_outcome(price_change_pct=-1.0))
        assert acc.expectancy == pytest.approx(0.8)

    def test_avg_mfe_pct(self):
        acc = _Acc()
        acc.add(_make_outcome(max_favorable_pct=2.0))
        acc.add(_make_outcome(max_favorable_pct=4.0))
        assert acc.avg_mfe_pct == pytest.approx(3.0)


# ── Engine integration tests ───────────────────────────────────────────────────

class TestStrategyFeedbackEngine:
    def test_empty_db_returns_empty_result(self):
        engine = _make_engine_with_rows([])
        result = engine.evaluate()
        assert result.total_outcomes == 0
        assert result.slices == []
        assert result.top_performers == []
        assert result.underperformers == []

    def test_single_observe_only_slice(self):
        """Fewer than 10 rows → OBSERVE_ONLY, not in top_performers or underperformers."""
        rows = [_make_outcome() for _ in range(5)]
        engine = _make_engine_with_rows(rows)
        result = engine.evaluate()
        assert result.total_outcomes == 5
        assert len(result.slices) == 1
        assert result.slices[0].recommendation == "OBSERVE_ONLY"
        assert result.top_performers == []
        assert result.underperformers == []

    def test_boost_slice_appears_in_top_performers(self):
        """30+ rows with high win rate, positive expectancy, PF>=1.5 → BOOST → in top_performers.

        Must include a few losses so profit_factor is defined (not None).
        25 wins at +2.0 pct, 5 losses at -0.5 pct → PF=20, wr=83%, exp>0.
        """
        win_rows = [
            _make_outcome(price_change_pct=2.0, max_adverse_pct=-0.3, max_favorable_pct=2.5)
            for _ in range(25)
        ]
        loss_rows = [
            _make_outcome(price_change_pct=-0.5, outcome_correct=False, max_adverse_pct=-0.5)
            for _ in range(5)
        ]
        engine = _make_engine_with_rows(win_rows + loss_rows)
        result = engine.evaluate()
        assert result.slices[0].recommendation == "BOOST"
        key = _slice_key("BTCUSDT", "1h", "trending", "BUY")
        assert key in result.top_performers

    def test_disable_slice_appears_in_underperformers(self):
        """20+ losses at poor rates → DISABLE → in underperformers."""
        rows = [
            _make_outcome(price_change_pct=-1.5, outcome_correct=False)
            for _ in range(20)
        ]
        engine = _make_engine_with_rows(rows)
        result = engine.evaluate()
        assert result.slices[0].recommendation == "DISABLE"
        key = _slice_key("BTCUSDT", "1h", "trending", "BUY")
        assert key in result.underperformers

    def test_summary_counts_match_slices(self):
        """Summary dict counts should equal actual slice breakdown."""
        # Create two distinct slices: one BOOST-worthy, one DISABLE-worthy
        win_rows = [
            _make_outcome(symbol="BTCUSDT", price_change_pct=2.0)
            for _ in range(30)
        ]
        lose_rows = [
            _make_outcome(symbol="ETHUSDT", price_change_pct=-1.5, outcome_correct=False)
            for _ in range(20)
        ]
        engine = _make_engine_with_rows(win_rows + lose_rows)
        result = engine.evaluate()
        total_from_summary = sum(result.summary.values())
        assert total_from_summary == len(result.slices)

    def test_regime_none_uses_any_key(self):
        """Outcomes with regime=None should be grouped under 'any' regime."""
        rows = [_make_outcome(regime=None) for _ in range(10)]
        engine = _make_engine_with_rows(rows)
        result = engine.evaluate()
        assert result.slices[0].regime is None
        assert result.slices[0].symbol == "BTCUSDT"

    def test_different_symbols_create_separate_slices(self):
        btc = [_make_outcome(symbol="BTCUSDT") for _ in range(5)]
        eth = [_make_outcome(symbol="ETHUSDT") for _ in range(5)]
        engine = _make_engine_with_rows(btc + eth)
        result = engine.evaluate()
        assert len(result.slices) == 2

    def test_lookback_days_passed_to_result(self):
        engine = _make_engine_with_rows([])
        result = engine.evaluate()
        assert result.lookback_days == 30

    def test_result_has_evaluated_at(self):
        engine = _make_engine_with_rows([])
        result = engine.evaluate()
        assert result.evaluated_at is not None
        assert result.evaluated_at.tzinfo is not None
