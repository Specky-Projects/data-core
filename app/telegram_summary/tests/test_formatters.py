"""Tests for Telegram summary formatters — pure function coverage.

All formatters are pure functions (payload → HTML string).
No DB, no network, no side effects.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.telegram_summary.dto import (
    AlertPayload,
    LongitudinalSummaryPayload,
    OperationalSummaryPayload,
    QuantSummaryPayload,
)
from app.telegram_summary.formatters.alert_formatter import format_alert
from app.telegram_summary.formatters.longitudinal_formatter import format_longitudinal_summary
from app.telegram_summary.formatters.operational_formatter import format_operational_summary
from app.telegram_summary.formatters.quant_formatter import format_quant_summary


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ts() -> datetime:
    return datetime(2026, 5, 27, 14, 0, 0, tzinfo=timezone.utc)


def _op(**kw) -> OperationalSummaryPayload:
    base = dict(
        status="OK",
        operational_status="HEALTHY",
        confidence_score=92,
        runtime_score=88,
        dataset_score=95,
        replayability_score=90,
        quant_reliability_score=87,
        infra_score=100,
        security_score=95,
        safe_mode=False,
        degradation_detected=False,
        critical_findings=[],
        warnings=[],
        generated_at=_ts(),
    )
    base.update(kw)
    return OperationalSummaryPayload(**base)


def _quant(**kw) -> QuantSummaryPayload:
    base = dict(
        total_outcomes=142,
        lookback_days=30,
        win_rate=0.623,
        expectancy=0.43,
        profit_factor=1.82,
        avg_return_pct=0.5,
        max_drawdown_pct=2.1,
        dominant_regime="trending",
        top_symbols=["BTCUSDT", "ETHUSDT"],
        overall_recommendation="KEEP",
        risk_level="LOW",
        boost_blocked=False,
        calibrated=True,
        generated_at=_ts(),
    )
    base.update(kw)
    return QuantSummaryPayload(**base)


def _long(**kw) -> LongitudinalSummaryPayload:
    base = dict(
        outcomes_24h=12,
        outcomes_7d=87,
        win_rate_24h=0.65,
        win_rate_7d=0.612,
        expectancy_24h=0.52,
        expectancy_7d=0.41,
        profit_factor_24h=2.1,
        profit_factor_7d=1.8,
        max_drawdown_24h=1.5,
        max_drawdown_7d=2.3,
        dominant_regime_24h="trending",
        dominant_regime_7d="ranging",
        generated_at=_ts(),
    )
    base.update(kw)
    return LongitudinalSummaryPayload(**base)


def _alert(**kw) -> AlertPayload:
    base = dict(
        alert_type="safe_mode_activated",
        severity="warning",
        title="Safe Mode Ativo",
        message="Sistema em Safe Mode.",
        details={"Score": "58/100"},
        generated_at=_ts(),
    )
    base.update(kw)
    return AlertPayload(**base)


# ── Operational formatter ──────────────────────────────────────────────────────

class TestOperationalFormatter:
    def test_returns_string(self):
        assert isinstance(format_operational_summary(_op()), str)

    def test_contains_title(self):
        assert "Resumo Operacional" in format_operational_summary(_op())

    def test_contains_timestamp(self):
        assert "14:00 UTC" in format_operational_summary(_op())

    def test_contains_confidence_score(self):
        assert "92" in format_operational_summary(_op())

    def test_contains_all_subscores(self):
        result = format_operational_summary(_op())
        assert "88" in result   # runtime
        assert "95" in result   # dataset
        assert "90" in result   # replayability
        assert "87" in result   # quant
        assert "100" in result  # infra

    def test_safe_mode_off(self):
        assert "off" in format_operational_summary(_op(safe_mode=False))

    def test_safe_mode_active(self):
        assert "ATIVO" in format_operational_summary(_op(safe_mode=True))

    def test_critical_status_icon(self):
        result = format_operational_summary(_op(status="CRITICAL"))
        assert "🔴" in result

    def test_critical_findings_listed(self):
        result = format_operational_summary(_op(critical_findings=["postgres down"]))
        assert "postgres down" in result

    def test_max_three_findings(self):
        findings = [f"finding-{i}" for i in range(10)]
        result = format_operational_summary(_op(critical_findings=findings))
        assert result.count("finding-") <= 3

    def test_finding_truncated_to_60_chars(self):
        long_finding = "x" * 100
        result = format_operational_summary(_op(critical_findings=[long_finding]))
        # Should not contain more than 60 x's from this finding
        assert "x" * 61 not in result

    def test_under_20_lines(self):
        result = format_operational_summary(_op(critical_findings=["a", "b", "c"]))
        assert len(result.splitlines()) <= 20

    def test_no_findings_under_20_lines(self):
        result = format_operational_summary(_op())
        assert len(result.splitlines()) <= 20

    def test_html_bold_tag_present(self):
        assert "<b>" in format_operational_summary(_op())

    def test_environment_shown(self):
        result = format_operational_summary(_op(environment="staging"))
        assert "staging" in result


# ── Quant formatter ────────────────────────────────────────────────────────────

class TestQuantFormatter:
    def test_returns_string(self):
        assert isinstance(format_quant_summary(_quant()), str)

    def test_contains_title(self):
        assert "Resumo Quant" in format_quant_summary(_quant())

    def test_contains_outcome_count(self):
        assert "142" in format_quant_summary(_quant())

    def test_win_rate_as_percent(self):
        result = format_quant_summary(_quant(win_rate=0.623))
        assert "62.3%" in result

    def test_boost_blocked_label(self):
        assert "bloqueado" in format_quant_summary(_quant(boost_blocked=True))

    def test_boost_allowed_label(self):
        assert "permitido" in format_quant_summary(_quant(boost_blocked=False))

    def test_none_win_rate_shows_na(self):
        assert "N/A" in format_quant_summary(_quant(win_rate=None))

    def test_none_profit_factor_shows_na(self):
        assert "N/A" in format_quant_summary(_quant(profit_factor=None))

    def test_top_symbols_shown(self):
        result = format_quant_summary(_quant(top_symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"]))
        assert "BTCUSDT" in result

    def test_at_most_3_top_symbols(self):
        result = format_quant_summary(_quant(top_symbols=["AAVEUSDT", "BNBUSDT", "CAKEUSDT", "DOTUSDT", "EGLDUSDT"]))
        assert "DOTUSDT" not in result
        assert "EGLDUSDT" not in result

    def test_risk_level_shown(self):
        result = format_quant_summary(_quant(risk_level="HIGH"))
        assert "HIGH" in result

    def test_recommendation_shown(self):
        result = format_quant_summary(_quant(overall_recommendation="THROTTLE"))
        assert "THROTTLE" in result

    def test_no_top_symbols_no_top_line(self):
        result = format_quant_summary(_quant(top_symbols=[]))
        assert "Top:" not in result

    def test_under_20_lines(self):
        result = format_quant_summary(_quant())
        assert len(result.splitlines()) <= 20

    def test_expectancy_positive_sign(self):
        result = format_quant_summary(_quant(expectancy=0.43))
        assert "+0.430" in result

    def test_expectancy_negative_sign(self):
        result = format_quant_summary(_quant(expectancy=-0.12))
        assert "-0.120" in result


# ── Longitudinal formatter ─────────────────────────────────────────────────────

class TestLongitudinalFormatter:
    def test_returns_string(self):
        assert isinstance(format_longitudinal_summary(_long()), str)

    def test_contains_title(self):
        assert "Resumo Longitudinal" in format_longitudinal_summary(_long())

    def test_contains_date(self):
        assert "27/05/2026" in format_longitudinal_summary(_long())

    def test_contains_24h_outcomes(self):
        assert "12" in format_longitudinal_summary(_long(outcomes_24h=12))

    def test_contains_7d_outcomes(self):
        assert "87" in format_longitudinal_summary(_long(outcomes_7d=87))

    def test_improvement_up_arrow(self):
        result = format_longitudinal_summary(_long(win_rate_24h=0.65, win_rate_7d=0.60))
        assert "⬆️" in result

    def test_decline_down_arrow(self):
        result = format_longitudinal_summary(_long(win_rate_24h=0.50, win_rate_7d=0.65))
        assert "⬇️" in result

    def test_equal_values_shows_approx(self):
        result = format_longitudinal_summary(
            _long(win_rate_24h=0.62, win_rate_7d=0.62)
        )
        assert "≈" in result

    def test_none_win_rate_shows_na(self):
        result = format_longitudinal_summary(_long(win_rate_24h=None, win_rate_7d=None))
        assert "N/A" in result

    def test_regime_shown(self):
        result = format_longitudinal_summary(_long(dominant_regime_24h="trending"))
        assert "trending" in result

    def test_under_20_lines(self):
        result = format_longitudinal_summary(_long())
        assert len(result.splitlines()) <= 20

    def test_none_regime_shows_na(self):
        result = format_longitudinal_summary(_long(dominant_regime_24h=None, dominant_regime_7d=None))
        assert "N/A" in result


# ── Alert formatter ────────────────────────────────────────────────────────────

class TestAlertFormatter:
    def test_returns_string(self):
        assert isinstance(format_alert(_alert()), str)

    def test_contains_title(self):
        assert "Safe Mode Ativo" in format_alert(_alert())

    def test_contains_message(self):
        assert "Sistema em Safe Mode" in format_alert(_alert())

    def test_warning_icon(self):
        assert "⚠️" in format_alert(_alert(severity="warning"))

    def test_critical_icon(self):
        assert "🚨" in format_alert(_alert(severity="critical"))

    def test_unknown_severity_fallback_icon(self):
        result = format_alert(_alert(severity="unknown"))
        assert "❔" in result

    def test_details_shown(self):
        result = format_alert(_alert(details={"Score": "42/100"}))
        assert "42/100" in result

    def test_details_key_shown(self):
        result = format_alert(_alert(details={"Score": "42/100"}))
        assert "Score" in result

    def test_max_5_details(self):
        details = {f"key{i}": f"val{i}" for i in range(10)}
        result = format_alert(_alert(details=details))
        assert result.count("key") <= 5

    def test_timestamp_shown(self):
        result = format_alert(_alert())
        assert "27/05/2026 14:00 UTC" in result

    def test_under_20_lines(self):
        details = {f"k{i}": f"v{i}" for i in range(5)}
        result = format_alert(_alert(details=details))
        assert len(result.splitlines()) <= 20

    def test_no_details_still_valid(self):
        result = format_alert(_alert(details={}))
        assert isinstance(result, str)
        assert len(result.splitlines()) <= 20
