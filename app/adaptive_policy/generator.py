"""AdaptivePolicyGenerator — synthesises AI + Operational Truth into a contract.

Input:
  - AdaptiveIntelligenceReport (Phase 9)
  - ProductionReadinessReport (Operational Truth, optional)
  - rollout_phase (int 1-4 from settings)
  - environment (str)

Output:
  - AdaptivePolicyContract

Fallback:
  - Any unhandled exception → OBSERVE_ONLY contract with safe defaults.
  - Missing truth report → degrade gracefully with conservative scores.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.adaptive_intelligence.dto import AdaptiveIntelligenceReport
from app.adaptive_policy.dto import (
    CONTRACT_TTL_SECONDS,
    AdaptivePolicyContract,
    EnforcementHints,
    allowed_actions_for,
    blocked_actions_for,
    desired_mode_from_optruth,
    desired_mode_from_risk,
    map_ai_risk,
    worst_mode,
)
from app.adaptive_policy.rollout import RolloutModeManager
from app.adaptive_policy.validator import ConfidenceSafetyValidator

logger = logging.getLogger(__name__)

# ── Safe fallback ──────────────────────────────────────────────────────────────

def _safe_fallback(environment: str, rollout_phase: int, reason: str) -> AdaptivePolicyContract:
    """Return a maximally conservative contract when generation fails."""
    now = datetime.now(timezone.utc)
    return AdaptivePolicyContract(
        generated_at=now,
        expires_at=now + timedelta(seconds=CONTRACT_TTL_SECONDS),
        environment=environment,
        status="WARNING",
        mode="OBSERVE_ONLY",
        safe_mode=False,
        fail_closed=False,
        kill_switch=False,
        confidence_score=0,
        replayability_score=0,
        quant_reliability_score=0,
        risk_level="HIGH",
        policy_hints=[f"fallback contract: {reason}"],
        allowed_actions=allowed_actions_for("OBSERVE_ONLY"),
        blocked_actions=blocked_actions_for("OBSERVE_ONLY"),
        enforcement_hints=EnforcementHints(
            disable_boost=True,
            reduce_position_size=False,
            increase_confirmation_threshold=True,
            disable_live_execution=False,
        ),
        warnings=[f"AdaptivePolicyGenerator failed: {reason}"],
        reasons=[reason],
        suggested_position_size_multiplier=1.0,
        suggested_min_confidence=65,
        boost_blocked=True,
        boost_block_reasons=[f"fallback: {reason}"],
        rollout_phase=rollout_phase,
        confidence_penalty_applied=0,
        uncertainty_penalty_applied=0,
    )


# ── Policy hint builder ───────────────────────────────────────────────────────

def _build_policy_hints(
    ai_report: AdaptiveIntelligenceReport,
    block_reasons: list[str],
    effective_mode: str,
    risk_level: str,
) -> list[str]:
    hints: list[str] = []

    if ai_report.strategy_feedback.top_performers:
        hints.append(
            f"top_performers: {', '.join(ai_report.strategy_feedback.top_performers[:3])}"
        )
    if ai_report.strategy_feedback.underperformers:
        hints.append(
            f"underperformers: {', '.join(ai_report.strategy_feedback.underperformers[:3])}"
        )
    if ai_report.regime.dominant_regime:
        hints.append(f"dominant_regime: {ai_report.regime.dominant_regime}")
    if ai_report.calibration.calibrated_threshold is not None:
        hints.append(
            f"calibrated_min_confidence: {ai_report.calibration.calibrated_threshold}"
        )
    if effective_mode == "SAFE_MODE":
        hints.append(
            f"safe_mode: reduce position size to "
            f"{ai_report.risk.suggested_position_size_multiplier:.0%}"
        )
    if block_reasons:
        hints.append(f"boost_blocked ({len(block_reasons)} reason(s))")

    hints.append(f"overall_risk: {risk_level} → mode: {effective_mode}")
    return hints


# ── Status computation ────────────────────────────────────────────────────────

def _compute_status(mode: str, confidence_score: int) -> str:
    if mode == "FAIL_CLOSED" or confidence_score < 40:
        return "CRITICAL"
    if mode in ("SAFE_MODE", "WARN_ONLY") or confidence_score < 65:
        return "WARNING"
    return "OK"


# ── Generator ─────────────────────────────────────────────────────────────────

class AdaptivePolicyGenerator:
    """Generate an AdaptivePolicyContract from AI + Operational Truth reports.

    Parameters
    ----------
    rollout_phase:
        Integer 1-4 controlling how far the contract can escalate.
    environment:
        Runtime environment label (e.g. "production", "staging").
    """

    def __init__(self, rollout_phase: int = 1, environment: str = "production") -> None:
        self._rollout_phase = rollout_phase
        self._environment = environment
        self._validator = ConfidenceSafetyValidator()
        self._rollout = RolloutModeManager(rollout_phase)

    # ------------------------------------------------------------------

    def generate(
        self,
        ai_report: AdaptiveIntelligenceReport,
        truth_report: Any | None = None,  # ProductionReadinessReport | None
    ) -> AdaptivePolicyContract:
        """Generate a policy contract from AI + Operational Truth reports.

        Parameters
        ----------
        ai_report:
            Output of AdaptiveIntelligenceOrchestrator.evaluate().
        truth_report:
            Output of ProductionReadinessService.evaluate() (optional).
            When None, conservative score defaults are used.
        """
        try:
            return self._generate_inner(ai_report, truth_report)
        except Exception as exc:
            logger.exception("adaptive_policy.generator: generation failed: %s", exc)
            return _safe_fallback(self._environment, self._rollout_phase, str(exc))

    # ------------------------------------------------------------------

    def _generate_inner(
        self,
        ai_report: AdaptiveIntelligenceReport,
        truth_report: Any | None,
    ) -> AdaptivePolicyContract:
        t0 = time.perf_counter()

        # ── Step 1: Extract truth scores ──────────────────────────────────────
        if truth_report is not None:
            confidence_score: int = int(truth_report.operational_confidence_score)
            replayability_score: int = int(truth_report.replayability_score)
            quant_reliability_score: int = int(truth_report.quant_reliability_score)
            operational_safe_mode: bool = bool(truth_report.safe_mode)
            operational_status: str = str(truth_report.operational_status)
        else:
            # No truth report → conservative defaults (degraded but not critical)
            confidence_score = 50
            replayability_score = 50
            quant_reliability_score = 50
            operational_safe_mode = False
            operational_status = "DEGRADED"
            logger.info("adaptive_policy.generator: no truth report — using conservative defaults")

        # ── Step 2: Run safety validation ─────────────────────────────────────
        validation = self._validator.validate(
            ai_report=ai_report,
            replayability_score=replayability_score,
            quant_reliability_score=quant_reliability_score,
            operational_safe_mode=operational_safe_mode,
        )

        # ── Step 3: Apply confidence penalties ────────────────────────────────
        adjusted_confidence = max(
            0,
            confidence_score - validation.confidence_penalty - validation.uncertainty_penalty,
        )

        # ── Step 4: Map risk level ─────────────────────────────────────────────
        risk_level = map_ai_risk(ai_report.risk.risk_level)

        # ── Step 5: Determine desired mode (worst of AI + operational truth) ──
        mode_from_risk = desired_mode_from_risk(risk_level)
        mode_from_truth = desired_mode_from_optruth(operational_status)
        desired = worst_mode(mode_from_risk, mode_from_truth)

        # ── Step 6: Apply rollout gate ─────────────────────────────────────────
        effective_mode = self._rollout.apply_gate(desired, risk_level)

        # ── Step 7: Safety flags ───────────────────────────────────────────────
        safe_mode = effective_mode in ("SAFE_MODE", "FAIL_CLOSED")
        fail_closed = effective_mode == "FAIL_CLOSED"
        kill_switch = False  # Adaptive policy never auto-activates kill_switch

        # ── Step 8: Actions ────────────────────────────────────────────────────
        allowed_actions = allowed_actions_for(effective_mode)
        blocked_actions = blocked_actions_for(effective_mode)

        # ── Step 9: Enforcement hints ──────────────────────────────────────────
        boost_blocked = not validation.boost_allowed
        enforcement_hints = EnforcementHints(
            disable_boost=boost_blocked or safe_mode,
            reduce_position_size=safe_mode,
            increase_confirmation_threshold=effective_mode in ("WARN_ONLY", "SAFE_MODE", "FAIL_CLOSED"),
            disable_live_execution=fail_closed,
        )

        # ── Step 10: Status ────────────────────────────────────────────────────
        status = _compute_status(effective_mode, adjusted_confidence)

        # ── Step 11: Narrative ─────────────────────────────────────────────────
        policy_hints = _build_policy_hints(
            ai_report, validation.block_reasons, effective_mode, risk_level
        )
        warnings = list(validation.warnings)
        reasons = list(ai_report.risk.reasoning)
        if validation.block_reasons:
            reasons = validation.block_reasons + reasons

        # ── Step 12: Assemble contract ─────────────────────────────────────────
        now = datetime.now(timezone.utc)
        contract = AdaptivePolicyContract(
            generated_at=now,
            expires_at=now + timedelta(seconds=CONTRACT_TTL_SECONDS),
            environment=self._environment,
            status=status,
            mode=effective_mode,
            safe_mode=safe_mode,
            fail_closed=fail_closed,
            kill_switch=kill_switch,
            confidence_score=adjusted_confidence,
            replayability_score=replayability_score,
            quant_reliability_score=quant_reliability_score,
            risk_level=risk_level,
            policy_hints=policy_hints,
            allowed_actions=allowed_actions,
            blocked_actions=blocked_actions,
            enforcement_hints=enforcement_hints,
            warnings=warnings,
            reasons=reasons[:20],  # cap for response size
            suggested_position_size_multiplier=ai_report.risk.suggested_position_size_multiplier,
            suggested_min_confidence=ai_report.risk.suggested_min_confidence,
            boost_blocked=boost_blocked,
            boost_block_reasons=validation.block_reasons,
            rollout_phase=self._rollout_phase,
            confidence_penalty_applied=validation.confidence_penalty,
            uncertainty_penalty_applied=validation.uncertainty_penalty,
        )

        elapsed = time.perf_counter() - t0
        logger.info(
            "adaptive_policy.generator: contract generated",
            extra={
                "mode": effective_mode,
                "status": status,
                "risk_level": risk_level,
                "boost_blocked": boost_blocked,
                "confidence_score": adjusted_confidence,
                "rollout_phase": self._rollout_phase,
                "duration_seconds": round(elapsed, 4),
            },
        )

        return contract
