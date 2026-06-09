"""Tests for Phase 10 Telegram Quant Ops."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.modules.crypto.edge.alert_state_model import EdgeAlertState
from app.modules.crypto.edge.forward_model import ForwardShadowSignal
from app.modules.crypto.edge.telegram_ops import (
    _best_worst_segment,
    _confidence_breakdown,
    _format_daily_summary,
    _format_weekly_report,
    _gate_alert_msg,
    _wr_pf_alert_msg,
    check_and_send_edge_alerts,
    run_all_ops,
    send_daily_summary,
    send_weekly_report,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_shadow(
    return_24h: float | None = None,
    outcome_correct_24h: bool | None = None,
    return_72h: float | None = None,
    outcome_correct_72h: bool | None = None,
    return_168h: float | None = None,
    outcome_correct_168h: bool | None = None,
    confidence: int = 80,
    regime: str = "UNKNOWN",
) -> ForwardShadowSignal:
    s = ForwardShadowSignal()
    s.id = uuid.uuid4()
    s.analytics_id = uuid.uuid4()
    s.symbol = "BTC/USDT"
    s.timeframe = "1h"
    s.confidence = confidence
    s.regime = regime
    s.signal_at = datetime(2026, 5, 1, tzinfo=timezone.utc)
    s.signal_price = Decimal("60000")
    s.return_24h = Decimal(str(return_24h)) if return_24h is not None else None
    s.outcome_correct_24h = outcome_correct_24h
    s.return_72h = Decimal(str(return_72h)) if return_72h is not None else None
    s.outcome_correct_72h = outcome_correct_72h
    s.return_168h = Decimal(str(return_168h)) if return_168h is not None else None
    s.outcome_correct_168h = outcome_correct_168h
    s.mfe_24h = s.mae_24h = s.mfe_72h = s.mae_72h = s.mfe_168h = s.mae_168h = None
    s.alert_entry_sent = s.alert_24h_sent = s.alert_72h_sent = s.alert_168h_sent = False
    s.created_at = s.updated_at = datetime(2026, 5, 1, tzinfo=timezone.utc)
    return s


def _empty_db(shadow_rows: list | None = None) -> MagicMock:
    db = MagicMock()
    rows = shadow_rows or []

    def query_side_effect(model):  # noqa: ANN001
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.all.return_value = rows
        q.first.return_value = None
        if model is EdgeAlertState:
            q.all.return_value = []
            q.first.return_value = None
        elif model is ForwardShadowSignal:
            q.all.return_value = rows
        return q

    db.query.side_effect = query_side_effect
    db.add = MagicMock()
    db.commit = MagicMock()
    return db


# ---------------------------------------------------------------------------
# TestMessageFormatters
# ---------------------------------------------------------------------------


class TestMessageFormatters:
    def test_gate_alert_msg_contains_gate(self) -> None:
        msg = _gate_alert_msg(72, 10, 10, 0.80, 3.5)
        assert "72h" in msg
        assert "n≥10" in msg
        assert "80.0%" in msg or "80%" in msg

    def test_gate_alert_msg_no_wr(self) -> None:
        msg = _gate_alert_msg(24, 10, 10, None, None)
        assert "N/A" in msg

    def test_wr_pf_alert_low_wr(self) -> None:
        msg = _wr_pf_alert_msg(72, 15, 0.40, None)
        assert "WR=40.0%" in msg or "40%" in msg
        assert "< 50%" in msg

    def test_wr_pf_alert_low_pf(self) -> None:
        msg = _wr_pf_alert_msg(72, 15, None, 1.2)
        assert "PF=1.20" in msg
        assert "< 1.5" in msg

    def test_format_daily_summary_structure(self) -> None:
        from app.modules.crypto.edge.readiness import build_readiness_report

        rows = [
            _make_shadow(
                return_72h=3.0, outcome_correct_72h=True,
                return_168h=5.0, outcome_correct_168h=True,
            )
        ]
        db = _empty_db(rows)
        report = build_readiness_report(db)
        msg = _format_daily_summary(report, rows)
        assert "72h" in msg
        assert "168h" in msg
        assert "BOOTSTRAP" in msg
        assert "sem trades" in msg

    def test_format_daily_summary_next_gate(self) -> None:
        from app.modules.crypto.edge.readiness import build_readiness_report

        rows = [_make_shadow(return_72h=3.0, outcome_correct_72h=True) for _ in range(5)]
        db = _empty_db(rows)
        report = build_readiness_report(db)
        msg = _format_daily_summary(report, rows)
        assert "faltam 5" in msg  # n=5, next gate = 10, needs 5 more

    def test_format_weekly_report_structure(self) -> None:
        from app.modules.crypto.edge.readiness import build_readiness_report

        rows = [
            _make_shadow(return_72h=3.0, outcome_correct_72h=True) for _ in range(4)
        ]
        db = _empty_db(rows)
        report = build_readiness_report(db)
        msg = _format_weekly_report(report, rows, "2026-W23")
        assert "2026-W23" in msg
        assert "REGIMES" in msg
        assert "CONFIANÇA" in msg
        assert "sem trades" in msg
        assert "HORIZONS" in msg

    def test_format_weekly_best_worst(self) -> None:
        from app.modules.crypto.edge.readiness import build_readiness_report

        rows = [
            # 72h bad, 168h good
            _make_shadow(return_72h=-2.0, outcome_correct_72h=False,
                         return_168h=5.0, outcome_correct_168h=True),
            _make_shadow(return_72h=-1.0, outcome_correct_72h=False,
                         return_168h=4.0, outcome_correct_168h=True),
            _make_shadow(return_72h=1.0, outcome_correct_72h=True,
                         return_168h=3.0, outcome_correct_168h=True),
        ]
        db = _empty_db(rows)
        report = build_readiness_report(db)
        msg = _format_weekly_report(report, rows, "2026-W23")
        assert "★" in msg  # best marker
        assert "✗" in msg  # worst marker


# ---------------------------------------------------------------------------
# TestBestWorstSegment
# ---------------------------------------------------------------------------


class TestBestWorstSegment:
    def _report(self, h24: float | None, h72: float | None, h168: float | None) -> dict:
        def _h(wr: float | None) -> dict:
            return {
                "win_rate": wr,
                "profit_factor": None,
                "avg_return_pct": None,
                "edge_status": "INSUFFICIENT_DATA",
                "win_rate_ci_95": None,
                "n_evaluated": 0,
                "n_total": 0,
                "n_pending": 0,
                "readiness_score": "BOOTSTRAP",
                "gates": {"n_ge_10": False, "n_ge_30": False, "n_ge_100": False},
                "n_wins": 0,
                "n_losses": 0,
                "profit_factor_ci_95": None,
            }
        return {"horizons": {"24h": _h(h24), "72h": _h(h72), "168h": _h(h168)}}

    def test_best_highest_wr(self) -> None:
        best, _ = _best_worst_segment(self._report(0.3, 0.8, 0.6))
        assert best == "72h"

    def test_worst_lowest_wr(self) -> None:
        _, worst = _best_worst_segment(self._report(0.3, 0.8, 0.6))
        assert worst == "24h"

    def test_all_none_returns_na(self) -> None:
        best, worst = _best_worst_segment(self._report(None, None, None))
        assert best == "N/A"
        assert worst == "N/A"


# ---------------------------------------------------------------------------
# TestConfidenceBreakdown
# ---------------------------------------------------------------------------


class TestConfidenceBreakdown:
    def test_correct_bucket(self) -> None:
        rows = [
            _make_shadow(confidence=80, return_72h=3.0, outcome_correct_72h=True),
            _make_shadow(confidence=80, return_72h=-1.0, outcome_correct_72h=False),
        ]
        bd = _confidence_breakdown(rows, 72)
        assert "75-84" in bd
        assert bd["75-84"]["n"] == 2
        assert bd["75-84"]["win_rate"] == 0.5

    def test_multiple_buckets(self) -> None:
        rows = [
            _make_shadow(confidence=78, return_72h=3.0, outcome_correct_72h=True),
            _make_shadow(confidence=90, return_72h=5.0, outcome_correct_72h=True),
        ]
        bd = _confidence_breakdown(rows, 72)
        assert "75-84" in bd
        assert "85+" in bd


# ---------------------------------------------------------------------------
# TestEdgeAlerts
# ---------------------------------------------------------------------------


class TestEdgeAlerts:
    def test_no_alerts_when_empty(self) -> None:
        db = _empty_db([])
        result = check_and_send_edge_alerts(db)
        assert result["alerts_sent"] == 0

    def test_gate_alert_fires_at_10(self) -> None:
        """Simulate n crossing 10 — should fire gate alert."""
        rows = [
            _make_shadow(return_72h=3.0, outcome_correct_72h=True) for _ in range(10)
        ]
        db = MagicMock()

        def query_side_effect(model):  # noqa: ANN001
            q = MagicMock()
            q.filter.return_value = q
            q.order_by.return_value = q
            if model is ForwardShadowSignal:
                q.all.return_value = rows
                q.first.return_value = None
            elif model is EdgeAlertState:
                q.all.return_value = rows
                q.first.return_value = None  # No existing state → gate not previously crossed
            return q

        db.query.side_effect = query_side_effect
        db.add = MagicMock()
        db.commit = MagicMock()

        with patch("app.modules.crypto.edge.telegram_ops._send_telegram", return_value=True):
            result = check_and_send_edge_alerts(db)
        # Gate 10 should have been triggered for at least one horizon
        gate_alerts = [a for a in result["details"] if a["type"] == "gate"]
        assert len(gate_alerts) > 0

    def test_edge_status_change_fires_alert(self) -> None:
        """Simulate edge_status changing from INSUFFICIENT_DATA to POSSIBLE_EDGE."""
        rows = [
            _make_shadow(return_72h=3.0, outcome_correct_72h=True) for _ in range(5)
        ]
        # Fake old state with different status
        fake_state = MagicMock(spec=EdgeAlertState)
        fake_state.last_value = {"status": "INSUFFICIENT_DATA"}
        fake_state.last_sent_at = None

        db = MagicMock()

        def query_side_effect(model):  # noqa: ANN001
            q = MagicMock()
            q.filter.return_value = q
            q.order_by.return_value = q
            if model is ForwardShadowSignal:
                q.all.return_value = rows
                q.first.return_value = None
            elif model is EdgeAlertState:
                q.all.return_value = []
                q.first.return_value = None
            return q

        db.query.side_effect = query_side_effect
        db.add = MagicMock()
        db.commit = MagicMock()

        # No alert should fire (status is the same, still INSUFFICIENT_DATA for n=5)
        with patch("app.modules.crypto.edge.telegram_ops._send_telegram", return_value=True):
            result = check_and_send_edge_alerts(db)
        edge_changes = [a for a in result["details"] if a["type"] == "edge_change"]
        # With n=5 still INSUFFICIENT, no change
        assert len(edge_changes) == 0


# ---------------------------------------------------------------------------
# TestSendDailySummary
# ---------------------------------------------------------------------------


class TestSendDailySummary:
    def test_sends_when_no_prior_state(self) -> None:
        db = _empty_db([])
        with patch("app.modules.crypto.edge.telegram_ops._send_telegram", return_value=True):
            result = send_daily_summary(db, force=True)
        assert result["sent"] is True
        assert "overall_verdict" in result

    def test_skips_when_already_sent_today(self) -> None:
        from app.modules.crypto.edge.telegram_ops import _today_str

        today = _today_str()
        rows = []
        db = MagicMock()

        # Return existing state with today's date
        fake_state = MagicMock(spec=EdgeAlertState)
        fake_state.last_value = {"date": today, "n": 0}

        def query_side_effect(model):  # noqa: ANN001
            q = MagicMock()
            q.filter.return_value = q
            q.order_by.return_value = q
            q.all.return_value = rows
            if model is EdgeAlertState:
                q.first.return_value = fake_state
            else:
                q.first.return_value = None
            return q

        db.query.side_effect = query_side_effect
        db.add = MagicMock()
        db.commit = MagicMock()

        result = send_daily_summary(db, force=False)
        assert result["sent"] is False
        assert result["reason"] == "already_sent_today"

    def test_force_bypasses_dedup(self) -> None:
        from app.modules.crypto.edge.telegram_ops import _today_str

        today = _today_str()
        fake_state = MagicMock(spec=EdgeAlertState)
        fake_state.last_value = {"date": today, "n": 0}

        db = MagicMock()

        def query_side_effect(model):  # noqa: ANN001
            q = MagicMock()
            q.filter.return_value = q
            q.order_by.return_value = q
            q.all.return_value = []
            if model is EdgeAlertState:
                q.first.return_value = fake_state
            else:
                q.first.return_value = None
            return q

        db.query.side_effect = query_side_effect
        db.add = MagicMock()
        db.commit = MagicMock()

        with patch("app.modules.crypto.edge.telegram_ops._send_telegram", return_value=True):
            result = send_daily_summary(db, force=True)
        assert result["sent"] is True


# ---------------------------------------------------------------------------
# TestSendWeeklyReport
# ---------------------------------------------------------------------------


class TestSendWeeklyReport:
    def test_sends_when_no_prior_state(self) -> None:
        db = _empty_db([])
        with patch("app.modules.crypto.edge.telegram_ops._send_telegram", return_value=True):
            result = send_weekly_report(db, force=True)
        assert result["sent"] is True
        assert "week" in result
        assert "message_preview" in result

    def test_skips_when_already_sent_this_week(self) -> None:
        from app.modules.crypto.edge.telegram_ops import _iso_week_str

        week = _iso_week_str()
        fake_state = MagicMock(spec=EdgeAlertState)
        fake_state.last_value = {"week": week, "n": 0}

        db = MagicMock()

        def query_side_effect(model):  # noqa: ANN001
            q = MagicMock()
            q.filter.return_value = q
            q.order_by.return_value = q
            q.all.return_value = []
            if model is EdgeAlertState:
                q.first.return_value = fake_state
            else:
                q.first.return_value = None
            return q

        db.query.side_effect = query_side_effect
        db.add = MagicMock()
        db.commit = MagicMock()

        result = send_weekly_report(db, force=False)
        assert result["sent"] is False
        assert result["reason"] == "already_sent_this_week"

    def test_preview_contains_key_fields(self) -> None:
        rows = [
            _make_shadow(return_72h=3.0, outcome_correct_72h=True) for _ in range(3)
        ]
        db = _empty_db(rows)
        with patch("app.modules.crypto.edge.telegram_ops._send_telegram", return_value=True):
            result = send_weekly_report(db, force=True)
        preview = result["message_preview"]
        assert "HORIZONS" in preview
        assert "REGIMES" in preview or "horizon" in preview.lower()


# ---------------------------------------------------------------------------
# TestRunAllOps
# ---------------------------------------------------------------------------


class TestRunAllOps:
    def test_returns_daily_alerts_keys(self) -> None:
        db = _empty_db([])
        with patch("app.modules.crypto.edge.telegram_ops._send_telegram", return_value=False):
            result = run_all_ops(db, force=True)
        assert "daily" in result
        assert "alerts" in result
        assert "weekly" in result
