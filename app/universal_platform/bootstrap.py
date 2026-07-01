"""Universal Platform — process lifecycle bootstrap.

Registers the Phase 2 Universal Platform into the application lifecycle without
altering any existing engine. Construction is:

    lazy         — deferred to first call, never runs at import time
    idempotent   — memoised; a second call never rebuilds or duplicates the runtime
    fail-safe    — any construction error is caught and logged; callers get a
                   clear "unavailable" state instead of a crash
    advisory_only — the platform never gates a request; absence degrades to
                   `initialized: false`, nothing more
    deterministic — the outcome (success or failure) is decided once per process
                   and never silently retried, so status() is stable across calls

No other component is touched by this module.
"""
from __future__ import annotations

import logging
from threading import Lock

from app.universal_platform.capabilities import Phase2Platform

logger = logging.getLogger(__name__)

_platform: Phase2Platform | None = None
_init_error: str | None = None
_lock = Lock()


def get_platform() -> Phase2Platform | None:
    """Return the process-wide Phase2Platform singleton, building it on first call.

    Returns ``None`` if construction failed (error is logged and cached) — callers
    must treat ``None`` as "platform unavailable" and degrade gracefully. Never
    raises.
    """
    global _platform, _init_error
    if _platform is not None or _init_error is not None:
        return _platform
    with _lock:
        if _platform is not None or _init_error is not None:
            return _platform
        try:
            platform = Phase2Platform()
            _platform = platform
            logger.info(
                "universal_platform.bootstrap: initialized (%d capabilities)",
                len(platform.orchestrator.registered_ids()),
            )
        except Exception as exc:  # noqa: BLE001 — must never block API boot
            _init_error = str(exc)
            logger.error("universal_platform.bootstrap: initialization failed: %s", exc)
    return _platform


def platform_status() -> dict:
    """Advisory status snapshot — safe to call regardless of init outcome."""
    platform = get_platform()
    if platform is None:
        return {
            "initialized": False,
            "error": _init_error,
            "advisory_only": True,
        }
    status = platform.status()
    status["initialized"] = True
    return status


def reset_for_tests() -> None:
    """Test-only hook to clear the memoised singleton between test cases."""
    global _platform, _init_error
    with _lock:
        _platform = None
        _init_error = None
