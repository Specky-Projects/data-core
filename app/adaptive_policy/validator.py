"""ConfidenceSafetyValidator — multi-signal BOOST guard and penalty engine.

Stateless: receives reports, emits a ValidationResult.
Never reads DB, never modifies state.

BOOST is blocked when ANY of the following is true:
  1. sample_size < MIN_SAMPLE_FOR_BOOST for any BOOST-recommended slice
  2. profit_factor is undefined (None) for any BOOST-recommended slice
  3. calibration.well_calibrated is False
  4. calibration.overconfidence_warning is True
  5. calibration slope is negative (reversed → calibration drift)
  6. replayability_score < REPLAYABILITY_BOOST_THRESHOLD (60)
  7. quant_reliability_score < QUANT_BOOST_THRESHOLD (60)
  8. operational safe_mode is active

Penalties are additive and subtracted from the raw confidence score before
it is published in the contract. This prevents artificially high confidence
scores from masking degraded underlying conditions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.adaptive_intelligence.dto import (
    MIN_SAMPLE_FOR_BOOST,
    AdaptiveIntelligenceReport,
    StrategySlice,
)

logger = logging.getLogger(__name__)

# ── Thresholds ─────────────────────────────────────────────────────────────────

REPLAYABILITY_BOOST_THRESHOLD = 60   # below → BOOST unsafe
QUANT_BOOST_THRESHOLD = 60           # below → entropy concern
REPLAYABILITY_PENALTY_BASELINE = 70  # below this → confidence penalty per 10 pts
QUANT_PENALTY_BASELINE = 70          # below this → confidence penalty per 10 pts

# Penalty magnitudes
_PENALTY_CALIBRATION_NOT_CALIBRATED = 10
_PENALTY_OVERCONFIDENCE = 15
_PENALTY_NEGATIVE_SLOPE = 10
_PENALTY_NO_CALIBRATED_THRESHOLD = 10
_PENALTY_UNDEFINED_PF_PER_SLICE = 5
_PENALTY_MAX_UNDEFINED_PF = 15

# Caps
_MAX_CONFIDENCE_PENALTY = 40
_MAX_UNCERTAINTY_PENALTY = 20


# ── Result ─────────────────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    boost_allowed: bool
    block_reasons: list[str] = field(default_factory=list)
    confidence_penalty: int = 0       # subtracted from raw confidence score
    uncertainty_penalty: int = 0      # additional structural uncertainty penalty
    warnings: list[str] = field(default_factory=list)


# ── Validator ─────────────────────────────────────────────────────────────────

class ConfidenceSafetyValidator:
    """Stateless multi-signal BOOST guard and confidence penalty engine."""

    def validate(
        self,
        ai_report: AdaptiveIntelligenceReport,
        replayability_score: int,
        quant_reliability_score: int,
        operational_safe_mode: bool,
    ) -> ValidationResult:
        block_reasons: list[str] = []
        warnings: list[str] = []
        confidence_penalty = 0
        uncertainty_penalty = 0

        strategy = ai_report.strategy_feedback
        calibration = ai_report.calibration

        # ── Extract BOOST slices ──────────────────────────────────────────────
        boost_slices: list[StrategySlice] = [
            s for s in strategy.slices if s.recommendation == "BOOST"
        ]

        # ── 1. Sample size check ──────────────────────────────────────────────
        low_sample_slices = [
            s for s in boost_slices if s.sample_size < MIN_SAMPLE_FOR_BOOST
        ]
        if low_sample_slices:
            block_reasons.append(
                f"{len(low_sample_slices)} BOOST slice(s) have sample_size < {MIN_SAMPLE_FOR_BOOST}"
            )

        # ── 2. Undefined profit factor ────────────────────────────────────────
        undef_pf_slices = [s for s in boost_slices if s.profit_factor is None]
        if undef_pf_slices:
            block_reasons.append(
                f"{len(undef_pf_slices)} BOOST slice(s) have undefined profit_factor (no losses)"
            )
            penalty = min(len(undef_pf_slices) * _PENALTY_UNDEFINED_PF_PER_SLICE, _PENALTY_MAX_UNDEFINED_PF)
            uncertainty_penalty += penalty

        # ── 3. Calibration not well calibrated ───────────────────────────────
        if not calibration.well_calibrated:
            block_reasons.append("confidence calibration is not well-calibrated")
            confidence_penalty += _PENALTY_CALIBRATION_NOT_CALIBRATED

        # ── 4. Overconfidence warning ─────────────────────────────────────────
        if calibration.overconfidence_warning:
            block_reasons.append("overconfidence warning: model confidence exceeds realized win rate")
            confidence_penalty += _PENALTY_OVERCONFIDENCE

        # ── 5. Negative calibration slope ─────────────────────────────────────
        slope = calibration.overall_calibration_slope
        if slope is not None and slope < 0:
            block_reasons.append(
                f"negative calibration slope ({slope:.4f}) — confidence is inversely predictive"
            )
            confidence_penalty += _PENALTY_NEGATIVE_SLOPE

        # ── 6. Replayability below threshold ─────────────────────────────────
        if replayability_score < REPLAYABILITY_BOOST_THRESHOLD:
            block_reasons.append(
                f"replayability_score={replayability_score} < {REPLAYABILITY_BOOST_THRESHOLD}"
            )
        if replayability_score < REPLAYABILITY_PENALTY_BASELINE:
            pts_below = REPLAYABILITY_PENALTY_BASELINE - replayability_score
            penalty = (pts_below // 10) * 5
            confidence_penalty += penalty
            warnings.append(
                f"replayability_score={replayability_score}: confidence penalised -{penalty}"
            )

        # ── 7. Quant reliability / entropy ────────────────────────────────────
        if quant_reliability_score < QUANT_BOOST_THRESHOLD:
            block_reasons.append(
                f"quant_reliability_score={quant_reliability_score} < {QUANT_BOOST_THRESHOLD}: entropy concern"
            )
        if quant_reliability_score < QUANT_PENALTY_BASELINE:
            pts_below = QUANT_PENALTY_BASELINE - quant_reliability_score
            penalty = (pts_below // 10) * 5
            confidence_penalty += penalty
            warnings.append(
                f"quant_reliability_score={quant_reliability_score}: confidence penalised -{penalty}"
            )

        # ── 8. Operational safe mode ──────────────────────────────────────────
        if operational_safe_mode:
            block_reasons.append("operational safe_mode is active")
            warnings.append("operational truth safe_mode propagated to adaptive policy")

        # ── Uncertainty: no calibrated threshold ──────────────────────────────
        if calibration.calibrated_threshold is None:
            uncertainty_penalty += _PENALTY_NO_CALIBRATED_THRESHOLD
            warnings.append("no calibrated confidence threshold established yet")

        # ── Cap penalties ──────────────────────────────────────────────────────
        confidence_penalty = min(confidence_penalty, _MAX_CONFIDENCE_PENALTY)
        uncertainty_penalty = min(uncertainty_penalty, _MAX_UNCERTAINTY_PENALTY)

        boost_allowed = len(block_reasons) == 0

        if block_reasons:
            logger.info(
                "adaptive_policy.validator: BOOST blocked",
                extra={
                    "block_reasons": block_reasons,
                    "confidence_penalty": confidence_penalty,
                    "uncertainty_penalty": uncertainty_penalty,
                },
            )

        return ValidationResult(
            boost_allowed=boost_allowed,
            block_reasons=block_reasons,
            confidence_penalty=confidence_penalty,
            uncertainty_penalty=uncertainty_penalty,
            warnings=warnings,
        )
