"""DTOs for the Adaptive Policy Contract layer.

The AdaptivePolicyContract synthesises:
  - Adaptive Intelligence (strategy feedback, calibration, regime, risk)
  - Operational Truth (confidence score, replayability, quant reliability)

into a single versioned, expirable contract that external services and
dashboards can consume.

Contract lifecycle:
  - TTL = CONTRACT_TTL_SECONDS (120 s)
  - Expired contract → consumer must treat as OBSERVE_ONLY
  - Version bump only on breaking changes; add fields freely
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

# ── Constants ──────────────────────────────────────────────────────────────────

CONTRACT_VERSION = "v1"
CONTRACT_TTL_SECONDS = 120

AdaptivePolicyStatus = Literal["OK", "WARNING", "CRITICAL"]
AdaptivePolicyMode   = Literal["OBSERVE_ONLY", "WARN_ONLY", "SAFE_MODE", "FAIL_CLOSED"]
PolicyRiskLevel      = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# Mode order used for escalation comparisons (index = severity)
MODE_ORDER: list[AdaptivePolicyMode] = ["OBSERVE_ONLY", "WARN_ONLY", "SAFE_MODE", "FAIL_CLOSED"]

# Canonical action taxonomy (same as operational enforcement layer).
ALL_ACTIONS: list[str] = [
    "data_read",
    "analytics_read",
    "data_write",
    "notification_send",
    "signal_generate",
    "position_open",
    "position_close",
]

# Actions blocked per mode — position_close is NEVER blocked.
_BLOCKED_BY_MODE: dict[str, list[str]] = {
    "OBSERVE_ONLY": [],
    "WARN_ONLY":    [],
    "SAFE_MODE":    [],           # sizing reduced, nothing hard-blocked
    "FAIL_CLOSED":  ["position_open"],
}

# AI layer risk→policy risk mapping
_AI_RISK_TO_POLICY: dict[str, PolicyRiskLevel] = {
    "LOW":      "LOW",
    "MODERATE": "MEDIUM",
    "HIGH":     "HIGH",
    "CRITICAL": "CRITICAL",
}

# Risk→desired mode (before rollout gate)
_RISK_TO_MODE: dict[str, AdaptivePolicyMode] = {
    "LOW":      "OBSERVE_ONLY",
    "MEDIUM":   "WARN_ONLY",
    "HIGH":     "SAFE_MODE",
    "CRITICAL": "FAIL_CLOSED",
}

# Operational truth status→desired mode
_OPTRUTH_TO_MODE: dict[str, AdaptivePolicyMode] = {
    "HEALTHY":          "OBSERVE_ONLY",
    "DEGRADED":         "WARN_ONLY",
    "PARTIALLY_UNSAFE": "SAFE_MODE",
    "UNSAFE":           "FAIL_CLOSED",
    "CRITICAL":         "FAIL_CLOSED",
}


def worst_mode(a: str, b: str) -> AdaptivePolicyMode:
    """Return the more restrictive of two mode strings."""
    ia = MODE_ORDER.index(a) if a in MODE_ORDER else 0
    ib = MODE_ORDER.index(b) if b in MODE_ORDER else 0
    return MODE_ORDER[max(ia, ib)]


def blocked_actions_for(mode: str) -> list[str]:
    return list(_BLOCKED_BY_MODE.get(mode, ["position_open"]))


def allowed_actions_for(mode: str) -> list[str]:
    blocked = set(blocked_actions_for(mode))
    return [a for a in ALL_ACTIONS if a not in blocked]


def map_ai_risk(ai_risk: str) -> PolicyRiskLevel:
    return _AI_RISK_TO_POLICY.get(ai_risk, "HIGH")


def desired_mode_from_risk(risk: str) -> AdaptivePolicyMode:
    return _RISK_TO_MODE.get(risk, "WARN_ONLY")


def desired_mode_from_optruth(status: str) -> AdaptivePolicyMode:
    return _OPTRUTH_TO_MODE.get(status, "WARN_ONLY")


# ── Sub-models ─────────────────────────────────────────────────────────────────

class EnforcementHints(BaseModel):
    """Structured hints for downstream enforcement consumers."""
    disable_boost: bool = True
    reduce_position_size: bool = False
    increase_confirmation_threshold: bool = False
    disable_live_execution: bool = False


# ── Main contract ──────────────────────────────────────────────────────────────

class AdaptivePolicyContract(BaseModel):
    """Versioned adaptive policy contract.

    Synthesises Adaptive Intelligence + Operational Truth into a single
    advisory document consumed by dashboards, enforcement hints, and operators.

    Advisory-only: this contract NEVER directly blocks trading actions.
    Downstream services decide whether to apply its hints.
    """

    # ── Identity & validity ───────────────────────────────────────────────────
    version: str = Field(default=CONTRACT_VERSION)
    generated_at: datetime
    expires_at: datetime
    environment: str

    # ── Status & mode ─────────────────────────────────────────────────────────
    status: AdaptivePolicyStatus
    mode: AdaptivePolicyMode

    # ── Safety flags ──────────────────────────────────────────────────────────
    safe_mode: bool
    fail_closed: bool
    kill_switch: bool = False    # Adaptive policy never auto-activates kill_switch

    # ── Scores (0-100) ────────────────────────────────────────────────────────
    confidence_score: int = Field(ge=0, le=100)
    replayability_score: int = Field(ge=0, le=100)
    quant_reliability_score: int = Field(ge=0, le=100)

    # ── Risk classification ───────────────────────────────────────────────────
    risk_level: PolicyRiskLevel

    # ── Actions ───────────────────────────────────────────────────────────────
    policy_hints: list[str]
    allowed_actions: list[str]
    blocked_actions: list[str]

    # ── Enforcement hints ──────────────────────────────────────────────────────
    enforcement_hints: EnforcementHints

    # ── Narrative ─────────────────────────────────────────────────────────────
    warnings: list[str]
    reasons: list[str]

    # ── Sizing / confidence hints (from RiskTuner) ────────────────────────────
    suggested_position_size_multiplier: float = Field(default=1.0, ge=0.0)
    suggested_min_confidence: int = Field(default=55, ge=0, le=100)

    # ── BOOST safety ──────────────────────────────────────────────────────────
    boost_blocked: bool = False
    boost_block_reasons: list[str] = Field(default_factory=list)

    # ── Rollout metadata ──────────────────────────────────────────────────────
    rollout_phase: int = 1

    # ── Penalty telemetry ─────────────────────────────────────────────────────
    confidence_penalty_applied: int = 0
    uncertainty_penalty_applied: int = 0

    # ─────────────────────────────────────────────────────────────────────────

    def is_expired(self, now: datetime | None = None) -> bool:
        _now = now or datetime.now(timezone.utc)
        return _now >= self.expires_at

    def to_summary(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "generated_at": self.generated_at.isoformat(),
            "status": self.status,
            "mode": self.mode,
            "risk_level": self.risk_level,
            "safe_mode": self.safe_mode,
            "fail_closed": self.fail_closed,
            "kill_switch": self.kill_switch,
            "confidence_score": self.confidence_score,
            "replayability_score": self.replayability_score,
            "quant_reliability_score": self.quant_reliability_score,
            "boost_blocked": self.boost_blocked,
            "suggested_position_size_multiplier": self.suggested_position_size_multiplier,
            "suggested_min_confidence": self.suggested_min_confidence,
            "rollout_phase": self.rollout_phase,
            "enforcement_hints": self.enforcement_hints.model_dump(),
        }
