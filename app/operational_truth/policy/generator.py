"""PolicyGenerator — builds an OperationalPolicyContract from a ProductionReadinessReport."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.operational_truth.dto import ProductionReadinessReport
from app.operational_truth.policy.contract import (
    CONTRACT_TTL_SECONDS,
    OperationalPolicyContract,
    allowed_actions_for,
    blocked_actions_for,
    default_enforcement_mode,
)
from app.operational_truth.safety import evaluate_safety

# Safe-mode position sizing: reduce to 50% of normal.
_SAFE_MODE_MULTIPLIER = 0.50

# Safe-mode minimum confidence override: raise threshold to 65.
_SAFE_MODE_MIN_CONFIDENCE = 65.0


def _build_degradation_reason(report: ProductionReadinessReport) -> str | None:
    if not report.critical_findings and not report.warnings:
        return None
    if report.critical_findings:
        return report.critical_findings[0]
    return report.warnings[0] if report.warnings else None


def generate_policy(report: ProductionReadinessReport) -> OperationalPolicyContract:
    """Build a versioned OperationalPolicyContract from a completed readiness report."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=CONTRACT_TTL_SECONDS)

    # Derive safety decision
    _confidence_proxy = type("C", (), {
        "operational_confidence_score": report.operational_confidence_score,
        "safe_mode": report.safe_mode,
        "infra_score": report.infra_score,
    })()
    safety = evaluate_safety(_confidence_proxy)

    mode = default_enforcement_mode(report.operational_status)
    blocked = blocked_actions_for(mode)
    allowed = allowed_actions_for(mode)

    # Sizing and confidence overrides (SAFE_MODE only)
    size_multiplier = 1.0
    min_conf_override = None
    if mode in ("safe_mode",):
        size_multiplier = _SAFE_MODE_MULTIPLIER
        min_conf_override = _SAFE_MODE_MIN_CONFIDENCE
    elif mode in ("fail_closed", "emergency_kill_switch"):
        size_multiplier = 0.0  # no new positions allowed anyway

    degradation_reason = _build_degradation_reason(report)

    return OperationalPolicyContract(
        generated_at=now,
        expires_at=expires_at,
        environment=report.environment,
        status=report.operational_status,
        confidence_score=report.operational_confidence_score,
        runtime_score=report.runtime_score,
        dataset_score=report.dataset_score,
        replayability_score=report.replayability_score,
        quant_reliability_score=report.quant_reliability_score,
        infra_score=report.infra_score,
        safe_mode=report.safe_mode,
        fail_closed=safety.fail_closed,
        kill_switch=safety.kill_switch,
        enforcement_mode=mode,
        allowed_actions=allowed,
        blocked_actions=blocked,
        degradation_reason=degradation_reason,
        critical_findings_count=len(report.critical_findings),
        warnings_count=len(report.warnings),
        position_size_multiplier=size_multiplier,
        min_confidence_override=min_conf_override,
    )
