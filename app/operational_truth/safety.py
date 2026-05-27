"""RuntimeSafetyEngine — safe mode detection, fail-closed logic, kill-switch."""

from __future__ import annotations

from dataclasses import dataclass

from app.operational_truth.dto import OperationalConfidence


@dataclass
class SafetyDecision:
    safe_mode: bool
    fail_closed: bool
    kill_switch: bool
    pressure_protection: bool
    reason: str
    severity: str  # "none" | "warning" | "critical" | "emergency"


_KILL_SWITCH_THRESHOLD = 15
_FAIL_CLOSED_THRESHOLD = 30
_PRESSURE_PROTECTION_THRESHOLD = 50


def evaluate_safety(confidence: OperationalConfidence) -> SafetyDecision:
    score = confidence.operational_confidence_score

    kill_switch = score <= _KILL_SWITCH_THRESHOLD
    fail_closed = score <= _FAIL_CLOSED_THRESHOLD or not _infra_ok(confidence)
    safe_mode = confidence.safe_mode
    pressure_protection = score <= _PRESSURE_PROTECTION_THRESHOLD

    if kill_switch:
        severity = "emergency"
        reason = f"Operational confidence critically low ({score}/100) — kill switch recommended"
    elif fail_closed:
        severity = "critical"
        reason = f"Operational confidence below fail-closed threshold ({score}/100)"
    elif safe_mode:
        severity = "critical"
        reason = f"Safe mode active: operational confidence {score}/100 < 40"
    elif pressure_protection:
        severity = "warning"
        reason = f"Pressure protection active: operational confidence {score}/100 < 50"
    else:
        severity = "none"
        reason = f"Runtime nominal: confidence {score}/100"

    return SafetyDecision(
        safe_mode=safe_mode,
        fail_closed=fail_closed,
        kill_switch=kill_switch,
        pressure_protection=pressure_protection,
        reason=reason,
        severity=severity,
    )


def _infra_ok(confidence: OperationalConfidence) -> bool:
    return confidence.infra_score >= 60
