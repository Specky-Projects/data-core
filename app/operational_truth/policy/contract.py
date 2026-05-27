"""OperationalPolicyContract — versioned safety decision exported at /policy/operational.

Design goals:
- Backward-compatible: add fields freely; never remove or rename existing ones.
- Conservative: any unknown or expired contract triggers safe_mode in the consumer.
- Auditable: every contract is timestamped and carries a short TTL (expires_at).
- Self-describing: enforcement_mode tells the consumer exactly what to do.

Version history:
  "1"  Initial release (2026-05-26)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CONTRACT_VERSION = "1"
CONTRACT_TTL_SECONDS = 120  # consumers treat an expired contract as stale → safe_mode

# Canonical action taxonomy consumed by downstream guards.
# Order matters for documentation; add new actions at the end.
ALL_ACTIONS: list[str] = [
    "data_read",          # Read from DB / API — always allowed
    "analytics_read",     # Compute/return analytics — always allowed
    "data_write",         # Write to DB / telemetry (restricted in FAIL_CLOSED)
    "notification_send",  # Send Telegram notifications
    "signal_generate",    # Generate + persist a trading signal (critical)
    "position_open",      # Open a new paper position (critical)
    "position_close",     # Close an existing position — always allowed
]

EnforcementMode = Literal[
    "observe_only",
    "warn_only",
    "safe_mode",
    "fail_closed",
    "emergency_kill_switch",
]

# Maps operational status → default enforcement mode.
# Downstream services may override this via their own env vars.
_STATUS_TO_MODE: dict[str, EnforcementMode] = {
    "HEALTHY":          "observe_only",
    "DEGRADED":         "warn_only",
    "PARTIALLY_UNSAFE": "safe_mode",
    "UNSAFE":           "fail_closed",
    "CRITICAL":         "emergency_kill_switch",
}

# Blocked actions per mode (complements are always allowed).
_BLOCKED_BY_MODE: dict[str, list[str]] = {
    "observe_only":           [],
    "warn_only":              [],
    "safe_mode":              [],                                     # sizing reduced, not blocked
    "fail_closed":            ["position_open"],
    "emergency_kill_switch":  ["position_open", "signal_generate"],
}


def default_enforcement_mode(operational_status: str) -> EnforcementMode:
    return _STATUS_TO_MODE.get(operational_status, "safe_mode")


def blocked_actions_for(mode: str) -> list[str]:
    return list(_BLOCKED_BY_MODE.get(mode, ["position_open", "signal_generate"]))


def allowed_actions_for(mode: str) -> list[str]:
    blocked = set(blocked_actions_for(mode))
    return [a for a in ALL_ACTIONS if a not in blocked]


class OperationalPolicyContract(BaseModel):
    """Versioned operational policy contract.

    Consumed by downstream services (poupi-crypto, poupi-baby, etc.) to decide
    whether to allow, warn, or block critical runtime actions.
    """

    # ── Identity & validity ───────────────────────────────────────────────────
    version: str = Field(default=CONTRACT_VERSION, description="Contract schema version")
    generated_at: datetime
    expires_at: datetime
    environment: str

    # ── Operational truth summary ─────────────────────────────────────────────
    status: str  # HEALTHY | DEGRADED | PARTIALLY_UNSAFE | UNSAFE | CRITICAL
    confidence_score: int = Field(ge=0, le=100)
    runtime_score: int = Field(ge=0, le=100)
    dataset_score: int = Field(ge=0, le=100)
    replayability_score: int = Field(ge=0, le=100)
    quant_reliability_score: int = Field(ge=0, le=100)
    infra_score: int = Field(ge=0, le=100)

    # ── Safety flags ──────────────────────────────────────────────────────────
    safe_mode: bool
    fail_closed: bool
    kill_switch: bool

    # ── Enforcement directive ─────────────────────────────────────────────────
    enforcement_mode: EnforcementMode
    allowed_actions: list[str]
    blocked_actions: list[str]

    # ── Context ───────────────────────────────────────────────────────────────
    degradation_reason: str | None = None
    critical_findings_count: int = 0
    warnings_count: int = 0

    # ── Sizing hint (for SAFE_MODE) ───────────────────────────────────────────
    # Downstream services should multiply their normal position sizes by this factor.
    # 1.0 = no change; 0.5 = half-size; 0.0 = block all sizing.
    position_size_multiplier: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Position size multiplier hint (1.0 = normal, 0.5 = half, 0.0 = none)",
    )

    # ── Min confidence override (for SAFE_MODE) ───────────────────────────────
    # If set, downstream should raise min_confidence to this value.
    min_confidence_override: float | None = Field(
        default=None, ge=0.0, le=100.0,
        description="Override min confidence threshold (None = use local default)",
    )

    def is_expired(self, now: datetime | None = None) -> bool:
        from datetime import timezone
        _now = now or datetime.now(timezone.utc)
        return _now >= self.expires_at

    def is_action_allowed(self, action: str) -> bool:
        return action not in self.blocked_actions

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "generated_at": self.generated_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "status": self.status,
            "confidence_score": self.confidence_score,
            "enforcement_mode": self.enforcement_mode,
            "safe_mode": self.safe_mode,
            "fail_closed": self.fail_closed,
            "kill_switch": self.kill_switch,
            "blocked_actions": self.blocked_actions,
        }
