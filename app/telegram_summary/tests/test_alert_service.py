"""Tests for AlertService — condition detection, cooldown, and deduplication."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.telegram_summary.dto import OperationalSummaryPayload
from app.telegram_summary.services.alert_service import AlertService


# ── Helpers ────────────────────────────────────────────────────────────────────

def _op(
    status: str = "OK",
    operational_status: str = "HEALTHY",
    confidence_score: int = 90,
    replayability_score: int = 90,
    quant_reliability_score: int = 80,
    safe_mode: bool = False,
) -> OperationalSummaryPayload:
    return OperationalSummaryPayload(
        status=status,
        operational_status=operational_status,
        confidence_score=confidence_score,
        runtime_score=85,
        dataset_score=90,
        replayability_score=replayability_score,
        quant_reliability_score=quant_reliability_score,
        infra_score=100,
        security_score=95,
        safe_mode=safe_mode,
        degradation_detected=False,
    )


# ── Condition detection ────────────────────────────────────────────────────────

class TestAlertConditions:
    def test_no_alerts_for_healthy_system(self):
        svc = AlertService()
        assert svc.evaluate(_op()) == []

    def test_critical_status_triggers_alert(self):
        svc = AlertService()
        alerts = svc.evaluate(_op(status="CRITICAL"))
        types = [a.alert_type for a in alerts]
        assert "system_critical" in types

    def test_critical_alert_severity_is_critical(self):
        svc = AlertService()
        alerts = svc.evaluate(_op(status="CRITICAL"))
        c = next(a for a in alerts if a.alert_type == "system_critical")
        assert c.severity == "critical"

    def test_safe_mode_triggers_alert(self):
        svc = AlertService()
        alerts = svc.evaluate(_op(safe_mode=True))
        types = [a.alert_type for a in alerts]
        assert "safe_mode_activated" in types

    def test_safe_mode_alert_is_warning(self):
        svc = AlertService()
        alerts = svc.evaluate(_op(safe_mode=True))
        sm = next(a for a in alerts if a.alert_type == "safe_mode_activated")
        assert sm.severity == "warning"

    def test_low_replayability_triggers_alert(self):
        svc = AlertService()
        alerts = svc.evaluate(_op(replayability_score=55))
        types = [a.alert_type for a in alerts]
        assert "low_replayability" in types

    def test_replayability_at_threshold_no_alert(self):
        svc = AlertService()
        alerts = svc.evaluate(_op(replayability_score=60))
        types = [a.alert_type for a in alerts]
        assert "low_replayability" not in types

    def test_quant_critical_triggers_alert(self):
        svc = AlertService()
        alerts = svc.evaluate(_op(quant_reliability_score=35))
        types = [a.alert_type for a in alerts]
        assert "quant_critical" in types

    def test_quant_at_threshold_no_alert(self):
        svc = AlertService()
        alerts = svc.evaluate(_op(quant_reliability_score=40))
        types = [a.alert_type for a in alerts]
        assert "quant_critical" not in types

    def test_low_confidence_triggers_alert(self):
        svc = AlertService()
        alerts = svc.evaluate(_op(confidence_score=45))
        types = [a.alert_type for a in alerts]
        assert "low_confidence" in types

    def test_confidence_at_threshold_no_alert(self):
        svc = AlertService()
        alerts = svc.evaluate(_op(confidence_score=50))
        types = [a.alert_type for a in alerts]
        assert "low_confidence" not in types

    def test_multiple_conditions_multiple_alerts(self):
        svc = AlertService()
        # critical status + safe_mode + low replayability simultaneously
        alerts = svc.evaluate(_op(
            status="CRITICAL",
            safe_mode=True,
            replayability_score=50,
        ))
        types = {a.alert_type for a in alerts}
        assert "system_critical" in types
        assert "safe_mode_activated" in types
        assert "low_replayability" in types

    def test_alert_has_title(self):
        svc = AlertService()
        alerts = svc.evaluate(_op(safe_mode=True))
        sm = next(a for a in alerts if a.alert_type == "safe_mode_activated")
        assert sm.title

    def test_alert_has_message(self):
        svc = AlertService()
        alerts = svc.evaluate(_op(safe_mode=True))
        sm = next(a for a in alerts if a.alert_type == "safe_mode_activated")
        assert sm.message

    def test_alert_has_details(self):
        svc = AlertService()
        alerts = svc.evaluate(_op(safe_mode=True))
        sm = next(a for a in alerts if a.alert_type == "safe_mode_activated")
        assert isinstance(sm.details, dict)


# ── Cooldown management ────────────────────────────────────────────────────────

class TestCooldown:
    def test_not_on_cooldown_initially(self):
        svc = AlertService()
        assert svc.is_on_cooldown("system_critical", "critical") is False

    def test_on_cooldown_immediately_after_mark_sent(self):
        svc = AlertService()
        svc.mark_sent("safe_mode_activated")
        assert svc.is_on_cooldown("safe_mode_activated", "warning") is True

    def test_not_on_cooldown_for_different_type(self):
        svc = AlertService()
        svc.mark_sent("safe_mode_activated")
        assert svc.is_on_cooldown("low_replayability", "warning") is False

    def test_alert_suppressed_after_mark_sent(self):
        svc = AlertService()
        op = _op(safe_mode=True)

        # First evaluation — not on cooldown
        alerts_1 = svc.evaluate(op)
        assert any(a.alert_type == "safe_mode_activated" for a in alerts_1)

        # Mark as sent
        svc.mark_sent("safe_mode_activated")

        # Second evaluation — suppressed
        alerts_2 = svc.evaluate(op)
        assert not any(a.alert_type == "safe_mode_activated" for a in alerts_2)

    def test_expired_cooldown_allows_resend(self):
        svc = AlertService()
        # Manually inject a timestamp 2h ago (well past 60min warning cooldown)
        svc._cooldown_state["safe_mode_activated"] = (
            datetime.now(timezone.utc) - timedelta(hours=2)
        )
        assert svc.is_on_cooldown("safe_mode_activated", "warning") is False

    def test_critical_cooldown_shorter_than_warning(self):
        """critical = 15min, warning = 60min."""
        svc = AlertService()
        # Set timestamp 20 minutes ago — should be off cooldown for critical (15min)
        # but still on cooldown for warning (60min)
        twenty_min_ago = datetime.now(timezone.utc) - timedelta(minutes=20)
        svc._cooldown_state["my_type"] = twenty_min_ago
        assert svc.is_on_cooldown("my_type", "critical") is False
        assert svc.is_on_cooldown("my_type", "warning") is True

    def test_mark_sent_updates_timestamp(self):
        svc = AlertService()
        old_ts = datetime.now(timezone.utc) - timedelta(hours=3)
        svc._cooldown_state["safe_mode_activated"] = old_ts
        # Now mark sent again
        svc.mark_sent("safe_mode_activated")
        # Cooldown should be active again
        assert svc.is_on_cooldown("safe_mode_activated", "warning") is True


# ── Deduplication via cooldown ─────────────────────────────────────────────────

class TestAlertDeduplication:
    def test_repeated_evaluate_calls_suppressed_after_send(self):
        """Simulate 3 hourly evaluations — alert only sent once per cooldown window."""
        svc = AlertService()
        op = _op(safe_mode=True)

        first = svc.evaluate(op)
        assert any(a.alert_type == "safe_mode_activated" for a in first)
        svc.mark_sent("safe_mode_activated")  # simulate successful send

        second = svc.evaluate(op)
        assert not any(a.alert_type == "safe_mode_activated" for a in second)

        third = svc.evaluate(op)
        assert not any(a.alert_type == "safe_mode_activated" for a in third)

    def test_different_alert_types_independent_cooldowns(self):
        svc = AlertService()
        op = _op(safe_mode=True, replayability_score=50)

        alerts = svc.evaluate(op)
        # Mark only safe_mode as sent
        svc.mark_sent("safe_mode_activated")

        alerts_2 = svc.evaluate(op)
        types = {a.alert_type for a in alerts_2}
        assert "safe_mode_activated" not in types    # on cooldown
        assert "low_replayability" in types          # still allowed
