"""Tests — SHORT/SELL sign inversion fix in _compute_group_metrics.

Verifica que SELL (short) ganho produz expectancy/PF positivos.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.modules.crypto.edge.calculator import _compute_group_metrics
from app.modules.crypto.edge.models import SignalEdgeOutcome


def _make_outcome(signal: str, pct: float, correct: bool) -> SignalEdgeOutcome:
    o = SignalEdgeOutcome()
    o.id = uuid.uuid4()
    o.analytics_id = uuid.uuid4()
    o.horizon_hours = 24
    o.symbol = "BTC/USDT"
    o.timeframe = "1h"
    o.signal = signal
    o.confidence = 80
    o.regime = "TRENDING_DOWN" if signal == "SELL" else "TRENDING_UP"
    o.price_change_pct = Decimal(str(pct))
    o.mfe_pct = Decimal(str(abs(pct) * 1.5))
    o.mae_pct = Decimal(str(abs(pct) * 0.5))
    o.outcome_correct = correct
    return o


class TestComputeGroupMetricsShortFix:
    def test_sell_win_positive_expectancy(self):
        """SELL (short) ganho: pct_change < 0 → expectancy > 0 após fix."""
        outcomes = [
            _make_outcome("SELL", -2.0, True),
            _make_outcome("SELL", -1.5, True),
            _make_outcome("SELL", -1.8, True),
            _make_outcome("SELL",  0.9, False),
        ]
        m = _compute_group_metrics(outcomes)
        assert m["win_rate"] == pytest.approx(0.75, abs=0.01)
        assert m["avg_return_pct"] > 0, (
            f"SELL ganho deve ter avg_return positivo após fix: {m['avg_return_pct']}"
        )
        assert m["expectancy"] > 0
        assert m["profit_factor"] is not None
        assert m["profit_factor"] > 1.0

    def test_buy_win_positive_expectancy_unchanged(self):
        """BUY ganho: pct_change > 0 → expectancy > 0 (comportamento preservado)."""
        outcomes = [
            _make_outcome("BUY", 2.0, True),
            _make_outcome("BUY", 1.5, True),
            _make_outcome("BUY", -0.8, False),
        ]
        m = _compute_group_metrics(outcomes)
        assert m["avg_return_pct"] > 0
        assert m["expectancy"] > 0

    def test_symmetric_buy_sell(self):
        """BUY e SELL com mesma magnitude → mesma expectancy."""
        buy_outcomes = [
            _make_outcome("BUY",  2.0, True),
            _make_outcome("BUY",  2.0, True),
            _make_outcome("BUY", -1.0, False),
        ]
        sell_outcomes = [
            _make_outcome("SELL", -2.0, True),
            _make_outcome("SELL", -2.0, True),
            _make_outcome("SELL",  1.0, False),
        ]
        m_buy  = _compute_group_metrics(buy_outcomes)
        m_sell = _compute_group_metrics(sell_outcomes)

        assert m_buy["expectancy"] == pytest.approx(m_sell["expectancy"], abs=0.01)
        assert m_buy["win_rate"]   == pytest.approx(m_sell["win_rate"],   abs=0.01)

    def test_sell_loss_negative_expectancy(self):
        """SELL perda: pct_change > 0, direction_correct=False → expectancy < 0."""
        outcomes = [
            _make_outcome("SELL",  1.5, False),
            _make_outcome("SELL",  1.2, False),
            _make_outcome("SELL", -0.5, True),
        ]
        m = _compute_group_metrics(outcomes)
        assert m["expectancy"] < 0
