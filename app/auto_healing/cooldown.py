"""Cooldown and Circuit Breaker for auto-healing restart actions.

Cooldown: prevents restart storms — max MAX_RESTARTS per WINDOW_SECONDS per service.
Circuit Breaker: after MAX_CONSECUTIVE consecutive healer failures, opens the circuit
and blocks further healing attempts for OPEN_TTL_SECONDS. Auto-resets after TTL.

State is stored in Redis using sorted sets (cooldown) and counters with TTL (circuit).
Falls back gracefully to ALLOW if Redis is unavailable (fail-open philosophy for
healing: we'd rather attempt an unsafe restart than leave a service dead permanently).
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_COOLDOWN_PREFIX = "auto_heal:cooldown:"
_CIRCUIT_FAILURES_PREFIX = "auto_heal:circuit:failures:"
_CIRCUIT_OPEN_PREFIX = "auto_heal:circuit:open:"

WINDOW_SECONDS = 30 * 60      # 30 minutes
MAX_RESTARTS = 3               # restarts allowed per window
MAX_CONSECUTIVE = 3            # consecutive failures before circuit opens
OPEN_TTL_SECONDS = 2 * 3600   # circuit stays open for 2 hours


@dataclass
class CooldownStatus:
    allowed: bool
    restarts_in_window: int
    max_restarts: int
    window_seconds: int
    reason: str = ""


@dataclass
class CircuitStatus:
    open: bool
    consecutive_failures: int
    reason: str = ""


def _redis_client():
    """Lazy import to avoid import-time dependency on Redis."""
    import redis as redis_lib
    from core.config import settings
    return redis_lib.from_url(settings.redis_url, socket_connect_timeout=2, decode_responses=True)


class CooldownManager:
    """Track restart counts per service within a rolling time window."""

    def __init__(self, window_seconds: int = WINDOW_SECONDS, max_restarts: int = MAX_RESTARTS) -> None:
        self.window_seconds = window_seconds
        self.max_restarts = max_restarts

    def check(self, service: str) -> CooldownStatus:
        """Return whether the service is within its cooldown budget."""
        try:
            client = _redis_client()
            key = f"{_COOLDOWN_PREFIX}{service}"
            now = time.time()
            cutoff = now - self.window_seconds

            # Remove expired entries and count remaining
            client.zremrangebyscore(key, "-inf", cutoff)
            count = client.zcard(key)
            allowed = count < self.max_restarts

            return CooldownStatus(
                allowed=allowed,
                restarts_in_window=count,
                max_restarts=self.max_restarts,
                window_seconds=self.window_seconds,
                reason="" if allowed else (
                    f"{count}/{self.max_restarts} restarts in last "
                    f"{self.window_seconds // 60}min — cooldown active"
                ),
            )
        except Exception as exc:
            logger.warning("cooldown.check failed for %s: %s — fail-open", service, exc)
            return CooldownStatus(
                allowed=True,
                restarts_in_window=0,
                max_restarts=self.max_restarts,
                window_seconds=self.window_seconds,
                reason="redis unavailable — fail-open",
            )

    def record_restart(self, service: str) -> None:
        """Record a restart attempt for the given service."""
        try:
            client = _redis_client()
            key = f"{_COOLDOWN_PREFIX}{service}"
            now = time.time()
            # Use UUID as member key to guarantee uniqueness even when called
            # multiple times within the same clock tick (low-res OS timer).
            member = uuid.uuid4().hex
            client.zadd(key, {member: now})
            # Keep the sorted set for 2× the window to allow inspection
            client.expire(key, self.window_seconds * 2)
        except Exception as exc:
            logger.warning("cooldown.record_restart failed for %s: %s", service, exc)

    def restart_count_in_window(self, service: str) -> int:
        """Return current restart count within the active window."""
        try:
            client = _redis_client()
            key = f"{_COOLDOWN_PREFIX}{service}"
            cutoff = time.time() - self.window_seconds
            client.zremrangebyscore(key, "-inf", cutoff)
            return int(client.zcard(key))
        except Exception:
            return 0

    def reset(self, service: str) -> None:
        """Clear cooldown state for a service (e.g. after manual recovery)."""
        try:
            _redis_client().delete(f"{_COOLDOWN_PREFIX}{service}")
        except Exception as exc:
            logger.warning("cooldown.reset failed for %s: %s", service, exc)


class CircuitBreaker:
    """Open circuit after MAX_CONSECUTIVE consecutive healer failures.

    Once open, no healing is attempted for OPEN_TTL_SECONDS. The circuit
    auto-resets after the TTL (half-open: next cycle gets one attempt).
    """

    def __init__(self, max_consecutive: int = MAX_CONSECUTIVE, open_ttl: int = OPEN_TTL_SECONDS) -> None:
        self.max_consecutive = max_consecutive
        self.open_ttl = open_ttl

    def status(self, service: str) -> CircuitStatus:
        """Return current circuit status for the given service."""
        try:
            client = _redis_client()
            open_key = f"{_CIRCUIT_OPEN_PREFIX}{service}"
            fail_key = f"{_CIRCUIT_FAILURES_PREFIX}{service}"

            if client.exists(open_key):
                ttl = client.ttl(open_key)
                count = int(client.get(fail_key) or 0)
                return CircuitStatus(
                    open=True,
                    consecutive_failures=count,
                    reason=f"circuit open ({ttl}s remaining) — {count} consecutive failures",
                )
            count = int(client.get(fail_key) or 0)
            return CircuitStatus(open=False, consecutive_failures=count)
        except Exception as exc:
            logger.warning("circuit.status failed for %s: %s — fail-open", service, exc)
            return CircuitStatus(open=False, consecutive_failures=0, reason="redis unavailable")

    def record_failure(self, service: str) -> CircuitStatus:
        """Record a healer failure and possibly open the circuit."""
        try:
            client = _redis_client()
            fail_key = f"{_CIRCUIT_FAILURES_PREFIX}{service}"
            open_key = f"{_CIRCUIT_OPEN_PREFIX}{service}"

            count = client.incr(fail_key)
            client.expire(fail_key, self.open_ttl * 2)

            if count >= self.max_consecutive and not client.exists(open_key):
                client.setex(open_key, self.open_ttl, "1")
                logger.warning(
                    "circuit_breaker: OPENED for service=%s after %d consecutive failures",
                    service, count,
                )
                return CircuitStatus(
                    open=True,
                    consecutive_failures=count,
                    reason=f"circuit OPENED after {count} consecutive failures",
                )
            return CircuitStatus(open=False, consecutive_failures=count)
        except Exception as exc:
            logger.warning("circuit.record_failure failed for %s: %s", service, exc)
            return CircuitStatus(open=False, consecutive_failures=0)

    def record_success(self, service: str) -> None:
        """Reset consecutive failure counter and close circuit."""
        try:
            client = _redis_client()
            client.delete(f"{_CIRCUIT_FAILURES_PREFIX}{service}")
            client.delete(f"{_CIRCUIT_OPEN_PREFIX}{service}")
        except Exception as exc:
            logger.warning("circuit.record_success failed for %s: %s", service, exc)

    def reset(self, service: str) -> None:
        """Manually reset circuit breaker (e.g. after operator confirms service healthy)."""
        self.record_success(service)
