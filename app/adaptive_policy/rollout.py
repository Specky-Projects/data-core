"""RolloutModeManager — incremental phase gate for adaptive policy escalation.

Rollout phases (configured via ADAPTIVE_POLICY_ROLLOUT_PHASE env var):

  Phase 1 — OBSERVE_ONLY
    Contract mode is always OBSERVE_ONLY regardless of risk.
    Pure observability: no policy hints acted upon, safe for day-1 deployment.

  Phase 2 — WARN_ONLY
    Contract mode can reach at most WARN_ONLY.
    Operators see structured warnings; no enforcement action taken.

  Phase 3 — SAFE_MODE_HINTS
    Contract mode can reach at most SAFE_MODE.
    Downstream enforcement may choose to apply sizing/confidence hints.
    FAIL_CLOSED is still gated.

  Phase 4 — FAIL_CLOSED_CRITICAL_ONLY
    FAIL_CLOSED is permitted only when risk_level == "CRITICAL".
    For HIGH/MEDIUM risk, mode is capped at SAFE_MODE.

Invariants:
  - Downgrade is always safe: reducing phase never blocks critical protection
  - Phase can be changed at runtime via config; no migration needed
  - Fallback: invalid phase → Phase 1 (OBSERVE_ONLY)
"""

from __future__ import annotations

import logging
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.adaptive_policy.dto import AdaptivePolicyMode, PolicyRiskLevel

logger = logging.getLogger(__name__)

_MODE_ORDER: list[str] = ["OBSERVE_ONLY", "WARN_ONLY", "SAFE_MODE", "FAIL_CLOSED"]


class RolloutPhase(IntEnum):
    OBSERVE_ONLY = 1
    WARN_ONLY = 2
    SAFE_MODE_HINTS = 3
    FAIL_CLOSED_CRITICAL_ONLY = 4


class RolloutModeManager:
    """Applies a phase gate to a desired mode, returning the effective mode.

    Parameters
    ----------
    phase:
        Integer phase (1-4). Values outside range are clamped to 1.
    """

    def __init__(self, phase: int = 1) -> None:
        try:
            self._phase = RolloutPhase(max(1, min(4, phase)))
        except ValueError:
            logger.warning(
                "adaptive_policy.rollout: invalid phase=%s, falling back to OBSERVE_ONLY", phase
            )
            self._phase = RolloutPhase.OBSERVE_ONLY

    # ------------------------------------------------------------------

    @property
    def phase(self) -> RolloutPhase:
        return self._phase

    @property
    def phase_name(self) -> str:
        return self._phase.name

    def apply_gate(self, desired_mode: str, risk_level: str = "LOW") -> str:
        """Return effective mode after applying rollout phase gate.

        Parameters
        ----------
        desired_mode:
            The mode computed from risk/operational truth before gating.
        risk_level:
            PolicyRiskLevel string; used in Phase 4 to gate FAIL_CLOSED.
        """
        if desired_mode not in _MODE_ORDER:
            logger.warning(
                "adaptive_policy.rollout: unknown mode %r, defaulting to OBSERVE_ONLY", desired_mode
            )
            return "OBSERVE_ONLY"

        desired_idx = _MODE_ORDER.index(desired_mode)

        if self._phase == RolloutPhase.OBSERVE_ONLY:
            return "OBSERVE_ONLY"

        if self._phase == RolloutPhase.WARN_ONLY:
            return _MODE_ORDER[min(desired_idx, 1)]  # cap at WARN_ONLY

        if self._phase == RolloutPhase.SAFE_MODE_HINTS:
            return _MODE_ORDER[min(desired_idx, 2)]  # cap at SAFE_MODE

        if self._phase == RolloutPhase.FAIL_CLOSED_CRITICAL_ONLY:
            if desired_mode == "FAIL_CLOSED" and risk_level != "CRITICAL":
                # FAIL_CLOSED only for CRITICAL risk; others cap at SAFE_MODE
                return "SAFE_MODE"
            return _MODE_ORDER[min(desired_idx, 3)]

        return "OBSERVE_ONLY"  # safe fallback

    def describe(self) -> dict[str, object]:
        """Human-readable rollout description for API consumers."""
        descriptions = {
            RolloutPhase.OBSERVE_ONLY: "Advisory only — no enforcement action. Safe for initial deployment.",
            RolloutPhase.WARN_ONLY: "Warn on degraded conditions. No blocking applied.",
            RolloutPhase.SAFE_MODE_HINTS: "May recommend safe_mode sizing/threshold hints.",
            RolloutPhase.FAIL_CLOSED_CRITICAL_ONLY: "Full escalation: FAIL_CLOSED only for CRITICAL risk.",
        }
        return {
            "phase": int(self._phase),
            "name": self._phase.name,
            "description": descriptions[self._phase],
            "max_mode": _MODE_ORDER[self._phase.value - 1],
        }
