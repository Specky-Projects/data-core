"""Tests for AutoHealingWatchdog Phase 2 components.

Coverage:
- CooldownManager: allow/block, record, reset, fail-open on Redis unavailable
- CircuitBreaker: allow/open, record_failure, record_success, auto-reset TTL
- ContainerHealer: can_heal routing, FAILED result when Docker unavailable
- WatchdogTelegramAlert endpoint: Alertmanager webhook → response shape
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.auto_healing.models import HealOutcome, HealResult, ServiceHealth


# ─── CooldownManager ─────────────────────────────────────────────────────────


class TestCooldownManager:
    """Uses a fake Redis to avoid real external dependency."""

    def _make_manager(self, fake_redis):
        from app.auto_healing.cooldown import CooldownManager
        manager = CooldownManager(window_seconds=1800, max_restarts=3)
        with patch("app.auto_healing.cooldown._redis_client", return_value=fake_redis):
            yield manager

    def _fake_redis(self):
        """Minimal in-memory Redis fake using a sorted set."""
        import time
        store: dict = {}
        expires: dict = {}

        class FakeRedis:
            def zremrangebyscore(self, key, _min, _max):
                if key not in store:
                    return
                store[key] = {k: v for k, v in store[key].items() if float(v) > float(_max)}

            def zcard(self, key):
                return len(store.get(key, {}))

            def zadd(self, key, mapping):
                store.setdefault(key, {}).update(mapping)

            def expire(self, key, seconds):
                expires[key] = seconds

            def delete(self, *keys):
                for k in keys:
                    store.pop(k, None)

            def exists(self, key):
                return int(key in store and bool(store[key]))

            def incr(self, key):
                store[key] = str(int(store.get(key, "0")) + 1)
                return int(store[key])

            def get(self, key):
                return store.get(key)

            def setex(self, key, ttl, value):
                store[key] = value
                expires[key] = ttl

            def ttl(self, key):
                return expires.get(key, -1)

        return FakeRedis()

    def test_initial_check_allowed(self):
        from app.auto_healing.cooldown import CooldownManager
        fake = self._fake_redis()
        with patch("app.auto_healing.cooldown._redis_client", return_value=fake):
            mgr = CooldownManager(window_seconds=1800, max_restarts=3)
            status = mgr.check("redis")
        assert status.allowed is True
        assert status.restarts_in_window == 0

    def test_block_after_max_restarts(self):
        from app.auto_healing.cooldown import CooldownManager
        fake = self._fake_redis()
        with patch("app.auto_healing.cooldown._redis_client", return_value=fake):
            mgr = CooldownManager(window_seconds=1800, max_restarts=3)
            # Record 3 restarts
            mgr.record_restart("redis")
            mgr.record_restart("redis")
            mgr.record_restart("redis")
            status = mgr.check("redis")
        assert status.allowed is False
        assert status.restarts_in_window == 3

    def test_reset_clears_state(self):
        from app.auto_healing.cooldown import CooldownManager
        fake = self._fake_redis()
        with patch("app.auto_healing.cooldown._redis_client", return_value=fake):
            mgr = CooldownManager(window_seconds=1800, max_restarts=3)
            mgr.record_restart("redis")
            mgr.record_restart("redis")
            mgr.record_restart("redis")
            mgr.reset("redis")
            status = mgr.check("redis")
        assert status.allowed is True

    def test_fail_open_on_redis_unavailable(self):
        from app.auto_healing.cooldown import CooldownManager
        with patch("app.auto_healing.cooldown._redis_client", side_effect=Exception("no redis")):
            mgr = CooldownManager()
            status = mgr.check("scheduler")
        assert status.allowed is True
        assert "fail-open" in status.reason

    def test_different_services_are_independent(self):
        from app.auto_healing.cooldown import CooldownManager
        fake = self._fake_redis()
        with patch("app.auto_healing.cooldown._redis_client", return_value=fake):
            mgr = CooldownManager(window_seconds=1800, max_restarts=3)
            mgr.record_restart("redis")
            mgr.record_restart("redis")
            mgr.record_restart("redis")
            redis_status = mgr.check("redis")
            scheduler_status = mgr.check("scheduler")
        assert redis_status.allowed is False
        assert scheduler_status.allowed is True


# ─── CircuitBreaker ───────────────────────────────────────────────────────────


class TestCircuitBreaker:
    def _fake_store(self):
        store: dict = {}
        expires: dict = {}

        class FakeRedis:
            def exists(self, key):
                return int(key in store)

            def incr(self, key):
                store[key] = str(int(store.get(key, "0")) + 1)
                return int(store[key])

            def expire(self, key, seconds):
                expires[key] = seconds

            def get(self, key):
                return store.get(key)

            def setex(self, key, ttl, value):
                store[key] = value
                expires[key] = ttl

            def ttl(self, key):
                return expires.get(key, -1)

            def delete(self, *keys):
                for k in keys:
                    store.pop(k, None)

        return FakeRedis()

    def test_initially_closed(self):
        from app.auto_healing.cooldown import CircuitBreaker
        fake = self._fake_store()
        with patch("app.auto_healing.cooldown._redis_client", return_value=fake):
            cb = CircuitBreaker(max_consecutive=3, open_ttl=7200)
            status = cb.status("scheduler")
        assert status.open is False
        assert status.consecutive_failures == 0

    def test_opens_after_max_consecutive_failures(self):
        from app.auto_healing.cooldown import CircuitBreaker
        fake = self._fake_store()
        with patch("app.auto_healing.cooldown._redis_client", return_value=fake):
            cb = CircuitBreaker(max_consecutive=3, open_ttl=7200)
            cb.record_failure("scheduler")
            cb.record_failure("scheduler")
            result = cb.record_failure("scheduler")  # 3rd → opens
        assert result.open is True
        assert result.consecutive_failures == 3

    def test_record_success_closes_circuit(self):
        from app.auto_healing.cooldown import CircuitBreaker
        fake = self._fake_store()
        with patch("app.auto_healing.cooldown._redis_client", return_value=fake):
            cb = CircuitBreaker(max_consecutive=3, open_ttl=7200)
            cb.record_failure("scheduler")
            cb.record_failure("scheduler")
            cb.record_failure("scheduler")
            cb.record_success("scheduler")
            status = cb.status("scheduler")
        assert status.open is False

    def test_fail_open_on_redis_unavailable(self):
        from app.auto_healing.cooldown import CircuitBreaker
        with patch("app.auto_healing.cooldown._redis_client", side_effect=Exception("no redis")):
            cb = CircuitBreaker()
            status = cb.status("redis")
        assert status.open is False

    def test_two_failures_do_not_open(self):
        from app.auto_healing.cooldown import CircuitBreaker
        fake = self._fake_store()
        with patch("app.auto_healing.cooldown._redis_client", return_value=fake):
            cb = CircuitBreaker(max_consecutive=3, open_ttl=7200)
            cb.record_failure("redis")
            result = cb.record_failure("redis")
        assert result.open is False


# ─── Container Healers ────────────────────────────────────────────────────────


class TestContainerHealers:
    def _down_health(self, name: str) -> ServiceHealth:
        return ServiceHealth(name=name, status="DOWN")

    def _up_health(self, name: str) -> ServiceHealth:
        return ServiceHealth(name=name, status="OK")

    # can_heal routing
    def test_redis_healer_can_heal_when_redis_down(self):
        from app.auto_healing.container_healer import RedisRestartHealer
        h = RedisRestartHealer()
        assert h.can_heal(self._down_health("redis")) is True
        assert h.can_heal(self._up_health("redis")) is False
        assert h.can_heal(self._down_health("scheduler")) is False

    def test_scheduler_healer_can_heal_when_scheduler_down(self):
        from app.auto_healing.container_healer import SchedulerRestartHealer
        h = SchedulerRestartHealer()
        assert h.can_heal(self._down_health("scheduler")) is True
        assert h.can_heal(self._up_health("scheduler")) is False

    def test_worker_healer_can_heal_when_worker_down(self):
        from app.auto_healing.container_healer import WorkerRestartHealer
        h = WorkerRestartHealer()
        assert h.can_heal(self._down_health("workers")) is True
        assert h.can_heal(self._up_health("workers")) is False

    def test_redis_healer_returns_failed_when_docker_unavailable(self):
        from app.auto_healing.container_healer import RedisRestartHealer
        h = RedisRestartHealer()
        with patch("app.auto_healing.container_healer._docker_client", side_effect=Exception("no docker")):
            result = h.heal(MagicMock())
        assert result.outcome == HealOutcome.FAILED
        assert result.service == "redis"

    def test_scheduler_healer_returns_failed_when_container_not_found(self):
        from app.auto_healing.container_healer import SchedulerRestartHealer
        h = SchedulerRestartHealer()
        with patch("app.auto_healing.container_healer._find_compose_container", return_value=None):
            result = h.heal(MagicMock())
        assert result.outcome == HealOutcome.FAILED
        assert "not found" in result.error.lower()

    def test_redis_healer_returns_recovered_when_restart_succeeds(self):
        from app.auto_healing.container_healer import RedisRestartHealer
        h = RedisRestartHealer()
        fake_container = MagicMock()
        fake_client = MagicMock()
        fake_client.containers.get.return_value = fake_container
        with (
            patch("app.auto_healing.container_healer._docker_client", return_value=fake_client),
            patch.dict("os.environ", {"REDIS_CONTAINER_NAME": "test-redis"}),
        ):
            result = h.heal(MagicMock())
        assert result.outcome == HealOutcome.RECOVERED
        fake_container.restart.assert_called_once_with(timeout=10)


# ─── Telegram Alert Endpoint ──────────────────────────────────────────────────


class TestTelegramAlertEndpoint:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from app.watchdog.api import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def _alertmanager_payload(self, status="firing", alert_name="RedisDown"):
        return {
            "version": "4",
            "groupKey": "test-group",
            "status": status,
            "receiver": "telegram-critical",
            "groupLabels": {"alertname": alert_name},
            "commonLabels": {"severity": "critical", "alertname": alert_name},
            "commonAnnotations": {"summary": "Redis is down"},
            "externalURL": "http://alertmanager:9093",
            "alerts": [
                {
                    "status": status,
                    "labels": {"alertname": alert_name, "severity": "critical"},
                    "annotations": {"summary": "Redis is down", "description": "Redis unreachable"},
                    "startsAt": "2026-06-08T10:00:00Z",
                    "endsAt": "0001-01-01T00:00:00Z",
                    "generatorURL": "http://prometheus:9090/alerts",
                }
            ],
        }

    def test_empty_alerts_returns_not_sent(self, client):
        payload = self._alertmanager_payload()
        payload["alerts"] = []
        resp = client.post("/api/v1/watchdog/telegram-alert", json=payload)
        assert resp.status_code == 200
        assert resp.json()["sent"] is False

    def test_firing_returns_200(self, client):
        payload = self._alertmanager_payload("firing")
        with patch("app.watchdog.api._send_telegram_message", return_value=True):
            resp = client.post("/api/v1/watchdog/telegram-alert", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["sent"] is True
        assert data["status"] == "firing"
        assert data["alerts"] == 1

    def test_resolved_returns_200(self, client):
        payload = self._alertmanager_payload("resolved")
        with patch("app.watchdog.api._send_telegram_message", return_value=True):
            resp = client.post("/api/v1/watchdog/telegram-alert", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    def test_telegram_send_failure_still_returns_200(self, client):
        """Alertmanager must not retry — always return 200 even on send failure."""
        payload = self._alertmanager_payload("firing")
        with patch("app.watchdog.api._send_telegram_message", return_value=False):
            resp = client.post("/api/v1/watchdog/telegram-alert", json=payload)
        assert resp.status_code == 200
        assert resp.json()["sent"] is False

    def test_format_includes_alert_name(self):
        from app.watchdog.api import _format_alertmanager_telegram, AlertmanagerWebhookPayload, _AlertmanagerAlert
        payload = AlertmanagerWebhookPayload(
            status="firing",
            alerts=[
                _AlertmanagerAlert(
                    status="firing",
                    labels={"alertname": "SchedulerStopped", "severity": "critical"},
                    annotations={"summary": "Scheduler heartbeat missing"},
                )
            ],
        )
        msg = _format_alertmanager_telegram(payload)
        assert "SchedulerStopped" in msg
        assert "Scheduler heartbeat missing" in msg
        assert "🔴" in msg


# ─── HealOutcome enum ─────────────────────────────────────────────────────────


def test_heal_outcome_has_blocked_circuit():
    from app.auto_healing.models import HealOutcome
    assert HealOutcome.BLOCKED_CIRCUIT == "BLOCKED_CIRCUIT"


def test_watchdog_execution_dry_run_not_hardcoded():
    """WatchdogExecution.to_dict() must reflect actual dry_run value."""
    from app.auto_healing.models import WatchdogExecution, GeneralStatus
    from datetime import datetime, timezone

    ex = WatchdogExecution(
        timestamp=datetime.now(timezone.utc),
        status=GeneralStatus.HEALTHY,
        dry_run=False,
        events=[],
        service_health=[],
    )
    assert ex.to_dict()["dry_run"] is False
