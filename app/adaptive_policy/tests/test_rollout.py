"""Tests for RolloutModeManager — phase gate logic."""

from __future__ import annotations

import pytest

from app.adaptive_policy.rollout import RolloutModeManager, RolloutPhase


class TestRolloutPhaseGate:
    # ── Phase 1: OBSERVE_ONLY ─────────────────────────────────────────────────

    def test_phase1_always_observe_only(self):
        mgr = RolloutModeManager(1)
        for desired in ["OBSERVE_ONLY", "WARN_ONLY", "SAFE_MODE", "FAIL_CLOSED"]:
            assert mgr.apply_gate(desired) == "OBSERVE_ONLY"

    def test_phase1_even_critical_risk_observe_only(self):
        mgr = RolloutModeManager(1)
        assert mgr.apply_gate("FAIL_CLOSED", "CRITICAL") == "OBSERVE_ONLY"

    # ── Phase 2: WARN_ONLY ────────────────────────────────────────────────────

    def test_phase2_observe_stays_observe(self):
        mgr = RolloutModeManager(2)
        assert mgr.apply_gate("OBSERVE_ONLY") == "OBSERVE_ONLY"

    def test_phase2_warn_only_allowed(self):
        mgr = RolloutModeManager(2)
        assert mgr.apply_gate("WARN_ONLY") == "WARN_ONLY"

    def test_phase2_safe_mode_capped_at_warn_only(self):
        mgr = RolloutModeManager(2)
        assert mgr.apply_gate("SAFE_MODE") == "WARN_ONLY"

    def test_phase2_fail_closed_capped_at_warn_only(self):
        mgr = RolloutModeManager(2)
        assert mgr.apply_gate("FAIL_CLOSED") == "WARN_ONLY"

    # ── Phase 3: SAFE_MODE_HINTS ──────────────────────────────────────────────

    def test_phase3_safe_mode_allowed(self):
        mgr = RolloutModeManager(3)
        assert mgr.apply_gate("SAFE_MODE") == "SAFE_MODE"

    def test_phase3_fail_closed_capped_at_safe_mode(self):
        mgr = RolloutModeManager(3)
        assert mgr.apply_gate("FAIL_CLOSED") == "SAFE_MODE"

    def test_phase3_warn_only_passes_through(self):
        mgr = RolloutModeManager(3)
        assert mgr.apply_gate("WARN_ONLY") == "WARN_ONLY"

    # ── Phase 4: FAIL_CLOSED_CRITICAL_ONLY ────────────────────────────────────

    def test_phase4_fail_closed_allowed_for_critical(self):
        mgr = RolloutModeManager(4)
        assert mgr.apply_gate("FAIL_CLOSED", "CRITICAL") == "FAIL_CLOSED"

    def test_phase4_fail_closed_capped_at_safe_mode_for_high_risk(self):
        mgr = RolloutModeManager(4)
        assert mgr.apply_gate("FAIL_CLOSED", "HIGH") == "SAFE_MODE"

    def test_phase4_fail_closed_capped_at_safe_mode_for_medium_risk(self):
        mgr = RolloutModeManager(4)
        assert mgr.apply_gate("FAIL_CLOSED", "MEDIUM") == "SAFE_MODE"

    def test_phase4_fail_closed_capped_at_safe_mode_for_low_risk(self):
        mgr = RolloutModeManager(4)
        assert mgr.apply_gate("FAIL_CLOSED", "LOW") == "SAFE_MODE"

    def test_phase4_safe_mode_and_below_pass_through(self):
        mgr = RolloutModeManager(4)
        assert mgr.apply_gate("SAFE_MODE") == "SAFE_MODE"
        assert mgr.apply_gate("WARN_ONLY") == "WARN_ONLY"
        assert mgr.apply_gate("OBSERVE_ONLY") == "OBSERVE_ONLY"

    # ── Invalid phase ─────────────────────────────────────────────────────────

    def test_invalid_phase_clamped_to_phase1(self):
        mgr = RolloutModeManager(0)
        # clamped to 1 (OBSERVE_ONLY)
        assert mgr.apply_gate("FAIL_CLOSED") == "OBSERVE_ONLY"

    def test_phase_above_4_clamped(self):
        mgr = RolloutModeManager(99)
        assert mgr.apply_gate("FAIL_CLOSED", "CRITICAL") == "FAIL_CLOSED"  # clamped to 4

    def test_unknown_mode_returns_observe_only(self):
        mgr = RolloutModeManager(4)
        assert mgr.apply_gate("INVALID_MODE") == "OBSERVE_ONLY"


class TestRolloutDescribe:
    def test_describe_returns_dict_with_required_keys(self):
        mgr = RolloutModeManager(1)
        desc = mgr.describe()
        assert "phase" in desc
        assert "name" in desc
        assert "description" in desc
        assert "max_mode" in desc

    def test_phase_property(self):
        mgr = RolloutModeManager(3)
        assert mgr.phase == RolloutPhase.SAFE_MODE_HINTS
        assert mgr.phase_name == "SAFE_MODE_HINTS"

    def test_max_mode_matches_phase(self):
        expected = {
            1: "OBSERVE_ONLY",
            2: "WARN_ONLY",
            3: "SAFE_MODE",
            4: "FAIL_CLOSED",
        }
        for phase, max_mode in expected.items():
            mgr = RolloutModeManager(phase)
            assert mgr.describe()["max_mode"] == max_mode


class TestRolloutMonotonic:
    """Higher phase always allows at least what lower phase allows."""

    def test_higher_phase_never_more_restrictive(self):
        """For a given desired_mode, applying a higher phase gives same or less restrictive result."""
        from app.adaptive_policy.dto import MODE_ORDER
        for desired in MODE_ORDER:
            results = [
                RolloutModeManager(p).apply_gate(desired, "CRITICAL")
                for p in range(1, 5)
            ]
            idxs = [MODE_ORDER.index(r) for r in results]
            # Indices should be non-decreasing (higher phase → same or more permissive)
            assert idxs == sorted(idxs), (
                f"desired={desired}: {list(zip(range(1, 5), results))} is not monotonic"
            )
