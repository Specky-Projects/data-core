"""Tests for the Universal Platform startup bootstrap — lazy, idempotent, fail-safe."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.universal_platform import bootstrap
from app.universal_platform.capabilities import PHASE2_CAPABILITY_IDS, Phase2Platform


@pytest.fixture(autouse=True)
def _reset_singleton():
    bootstrap.reset_for_tests()
    yield
    bootstrap.reset_for_tests()


def test_get_platform_returns_a_platform() -> None:
    platform = bootstrap.get_platform()
    assert isinstance(platform, Phase2Platform)


def test_get_platform_is_idempotent() -> None:
    p1 = bootstrap.get_platform()
    p2 = bootstrap.get_platform()
    assert p1 is p2  # no parallel runtime is ever created


def test_get_platform_is_lazy_until_first_call() -> None:
    # module state starts empty until get_platform() is invoked
    assert bootstrap._platform is None
    assert bootstrap._init_error is None
    bootstrap.get_platform()
    assert bootstrap._platform is not None


def test_get_platform_fail_safe_on_construction_error() -> None:
    with patch("app.universal_platform.bootstrap.Phase2Platform", side_effect=RuntimeError("boom")):
        platform = bootstrap.get_platform()
    assert platform is None  # never raises


def test_get_platform_deterministic_no_retry_after_failure() -> None:
    with patch("app.universal_platform.bootstrap.Phase2Platform", side_effect=RuntimeError("boom")):
        bootstrap.get_platform()
    with patch("app.universal_platform.bootstrap.Phase2Platform", side_effect=AssertionError("must not retry")) as m:
        result = bootstrap.get_platform()
    assert result is None
    m.assert_not_called()


def test_platform_status_when_initialized() -> None:
    status = bootstrap.platform_status()
    assert status["initialized"] is True
    assert status["advisory_only"] is True
    assert status["shadow_mode"] is True
    assert status["read_only"] is True
    assert set(status["capabilities"]) == set(PHASE2_CAPABILITY_IDS)


def test_platform_status_when_construction_failed() -> None:
    with patch("app.universal_platform.bootstrap.Phase2Platform", side_effect=RuntimeError("boom")):
        status = bootstrap.platform_status()
    assert status == {"initialized": False, "error": "boom", "advisory_only": True}


def test_reset_for_tests_allows_recovery() -> None:
    with patch("app.universal_platform.bootstrap.Phase2Platform", side_effect=RuntimeError("boom")):
        bootstrap.get_platform()
    assert bootstrap.get_platform() is None
    bootstrap.reset_for_tests()
    assert bootstrap.get_platform() is not None
