"""Tests for cooldown thread safety and singleton behavior."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

import pytest

from app.telegram_summary.dto import OperationalSummaryPayload
from app.telegram_summary.services.alert_service import AlertService, get_alert_service


def _healthy_op() -> OperationalSummaryPayload:
    return OperationalSummaryPayload(
        status="OK",
        operational_status="HEALTHY",
        confidence_score=90,
        runtime_score=90,
        dataset_score=90,
        replayability_score=90,
        quant_reliability_score=90,
        infra_score=100,
        security_score=100,
        safe_mode=False,
        degradation_detected=False,
    )


class TestCooldownThreadSafety:
    def test_concurrent_mark_sent_no_exceptions(self):
        """20 threads marking the same alert_type simultaneously must not raise."""
        svc = AlertService()
        errors: list[Exception] = []

        def _mark() -> None:
            try:
                svc.mark_sent("system_critical")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_mark) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert svc.is_on_cooldown("system_critical", "critical") is True

    def test_concurrent_is_on_cooldown_no_exceptions(self):
        """Mixed reads and writes from multiple threads must not raise."""
        svc = AlertService()
        svc.mark_sent("safe_mode_activated")
        errors: list[Exception] = []

        def _read() -> None:
            try:
                svc.is_on_cooldown("safe_mode_activated", "warning")
            except Exception as exc:
                errors.append(exc)

        def _write() -> None:
            try:
                svc.mark_sent("safe_mode_activated")
            except Exception as exc:
                errors.append(exc)

        threads = (
            [threading.Thread(target=_read) for _ in range(10)]
            + [threading.Thread(target=_write) for _ in range(10)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

    def test_concurrent_evaluate_no_exceptions(self):
        """Concurrent evaluate() calls on a healthy payload must not raise."""
        svc = AlertService()
        op = _healthy_op()
        errors: list[Exception] = []

        def _eval() -> None:
            try:
                svc.evaluate(op)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_eval) for _ in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

    def test_concurrent_mark_and_evaluate(self):
        """Interleaved mark_sent and evaluate must not corrupt state."""
        svc = AlertService()
        errors: list[Exception] = []
        op = _healthy_op()

        def _mark_and_eval() -> None:
            try:
                svc.mark_sent("low_confidence")
                svc.evaluate(op)
                svc.is_on_cooldown("low_confidence", "warning")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_mark_and_eval) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors


class TestSingleton:
    def test_get_alert_service_returns_same_instance(self):
        """get_alert_service() returns the same object every call."""
        a = get_alert_service()
        b = get_alert_service()
        assert a is b

    def test_singleton_thread_safe(self):
        """Multiple threads calling get_alert_service() concurrently get the same instance."""
        instances: list[AlertService] = []

        def _get() -> None:
            instances.append(get_alert_service())

        threads = [threading.Thread(target=_get) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All IDs must be equal — one singleton
        assert len({id(i) for i in instances}) == 1

    def test_singleton_state_shared_across_calls(self):
        """State marked in one reference is visible from another reference."""
        svc_a = get_alert_service()
        svc_b = get_alert_service()

        # Mark via svc_a, read via svc_b
        svc_a.mark_sent("quant_critical")
        assert svc_b.is_on_cooldown("quant_critical", "critical") is True
