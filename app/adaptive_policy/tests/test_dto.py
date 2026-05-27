"""Tests for AdaptivePolicyContract DTO helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.adaptive_policy.dto import (
    AdaptivePolicyContract,
    EnforcementHints,
    CONTRACT_VERSION,
    allowed_actions_for,
    blocked_actions_for,
    desired_mode_from_optruth,
    desired_mode_from_risk,
    map_ai_risk,
    worst_mode,
    MODE_ORDER,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _contract(
    mode: str = "OBSERVE_ONLY",
    status: str = "OK",
    risk_level: str = "LOW",
    safe_mode: bool = False,
    fail_closed: bool = False,
    confidence_score: int = 80,
    boost_blocked: bool = False,
    expires_delta_seconds: int = 120,
) -> AdaptivePolicyContract:
    now = _now()
    return AdaptivePolicyContract(
        generated_at=now,
        expires_at=now + timedelta(seconds=expires_delta_seconds),
        environment="test",
        status=status,
        mode=mode,
        safe_mode=safe_mode,
        fail_closed=fail_closed,
        confidence_score=confidence_score,
        replayability_score=80,
        quant_reliability_score=80,
        risk_level=risk_level,
        policy_hints=[],
        allowed_actions=allowed_actions_for(mode),
        blocked_actions=blocked_actions_for(mode),
        enforcement_hints=EnforcementHints(),
        warnings=[],
        reasons=[],
        boost_blocked=boost_blocked,
    )


# ── Mode helpers ───────────────────────────────────────────────────────────────

class TestModeHelpers:
    def test_worst_mode_same_returns_same(self):
        assert worst_mode("OBSERVE_ONLY", "OBSERVE_ONLY") == "OBSERVE_ONLY"
        assert worst_mode("FAIL_CLOSED", "FAIL_CLOSED") == "FAIL_CLOSED"

    def test_worst_mode_picks_more_restrictive(self):
        assert worst_mode("OBSERVE_ONLY", "FAIL_CLOSED") == "FAIL_CLOSED"
        assert worst_mode("WARN_ONLY", "SAFE_MODE") == "SAFE_MODE"
        assert worst_mode("SAFE_MODE", "WARN_ONLY") == "SAFE_MODE"

    def test_worst_mode_all_combinations_monotonic(self):
        for i, a in enumerate(MODE_ORDER):
            for j, b in enumerate(MODE_ORDER):
                result = worst_mode(a, b)
                expected_idx = max(i, j)
                assert result == MODE_ORDER[expected_idx]

    def test_map_ai_risk_all_values(self):
        assert map_ai_risk("LOW") == "LOW"
        assert map_ai_risk("MODERATE") == "MEDIUM"
        assert map_ai_risk("HIGH") == "HIGH"
        assert map_ai_risk("CRITICAL") == "CRITICAL"

    def test_map_ai_risk_unknown_defaults_to_high(self):
        assert map_ai_risk("UNKNOWN") == "HIGH"

    def test_desired_mode_from_risk(self):
        assert desired_mode_from_risk("LOW") == "OBSERVE_ONLY"
        assert desired_mode_from_risk("MEDIUM") == "WARN_ONLY"
        assert desired_mode_from_risk("HIGH") == "SAFE_MODE"
        assert desired_mode_from_risk("CRITICAL") == "FAIL_CLOSED"

    def test_desired_mode_from_optruth(self):
        assert desired_mode_from_optruth("HEALTHY") == "OBSERVE_ONLY"
        assert desired_mode_from_optruth("DEGRADED") == "WARN_ONLY"
        assert desired_mode_from_optruth("PARTIALLY_UNSAFE") == "SAFE_MODE"
        assert desired_mode_from_optruth("UNSAFE") == "FAIL_CLOSED"
        assert desired_mode_from_optruth("CRITICAL") == "FAIL_CLOSED"
        assert desired_mode_from_optruth("UNKNOWN") == "WARN_ONLY"


class TestActionHelpers:
    def test_observe_only_no_blocked_actions(self):
        assert blocked_actions_for("OBSERVE_ONLY") == []

    def test_fail_closed_blocks_position_open(self):
        blocked = blocked_actions_for("FAIL_CLOSED")
        assert "position_open" in blocked
        assert "position_close" not in blocked
        assert "signal_generate" not in blocked  # only operational kill_switch

    def test_safe_mode_no_blocked_actions(self):
        blocked = blocked_actions_for("SAFE_MODE")
        assert blocked == []  # sizing reduced but nothing hard-blocked

    def test_allowed_actions_complement_blocked(self):
        for mode in ["OBSERVE_ONLY", "WARN_ONLY", "SAFE_MODE", "FAIL_CLOSED"]:
            allowed = set(allowed_actions_for(mode))
            blocked = set(blocked_actions_for(mode))
            assert allowed & blocked == set(), f"overlap in {mode}"

    def test_position_close_always_allowed(self):
        for mode in ["OBSERVE_ONLY", "WARN_ONLY", "SAFE_MODE", "FAIL_CLOSED"]:
            assert "position_close" in allowed_actions_for(mode)


# ── Contract ──────────────────────────────────────────────────────────────────

class TestAdaptivePolicyContract:
    def test_default_version(self):
        c = _contract()
        assert c.version == CONTRACT_VERSION

    def test_not_expired_when_fresh(self):
        c = _contract(expires_delta_seconds=120)
        assert not c.is_expired()

    def test_expired_when_past(self):
        c = _contract(expires_delta_seconds=-1)
        assert c.is_expired()

    def test_to_summary_contains_required_keys(self):
        c = _contract()
        s = c.to_summary()
        required = {
            "version", "generated_at", "status", "mode", "risk_level",
            "safe_mode", "fail_closed", "kill_switch", "confidence_score",
            "replayability_score", "quant_reliability_score",
            "boost_blocked", "suggested_position_size_multiplier",
            "suggested_min_confidence", "rollout_phase", "enforcement_hints",
        }
        assert required.issubset(s.keys())

    def test_kill_switch_always_false_in_adaptive_policy(self):
        """Adaptive Policy NEVER auto-activates kill_switch."""
        c = _contract(mode="FAIL_CLOSED", fail_closed=True)
        assert c.kill_switch is False

    def test_safe_mode_flag_consistent_with_mode(self):
        c_safe = _contract(mode="SAFE_MODE", safe_mode=True)
        c_obs = _contract(mode="OBSERVE_ONLY", safe_mode=False)
        assert c_safe.safe_mode is True
        assert c_obs.safe_mode is False

    def test_enforcement_hints_model(self):
        hints = EnforcementHints(
            disable_boost=True,
            reduce_position_size=True,
            increase_confirmation_threshold=True,
            disable_live_execution=False,
        )
        assert hints.disable_boost is True
        assert hints.disable_live_execution is False
