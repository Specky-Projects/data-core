"""AdaptiveIntelligenceOrchestrator — runs all four engines in sequence.

Never breaks the trading runtime:
  - Each engine failure is caught and logged; a degraded result is returned.
  - Metrics are published best-effort (failures silently ignored).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.adaptive_intelligence.confidence_calibration import ConfidenceCalibrationEngine
from app.adaptive_intelligence.dto import (
    AdaptiveIntelligenceReport,
    ConfidenceCalibrationResult,
    Recommendation,
    RegimeAdapterResult,
    RiskTuningResult,
    StrategyFeedbackResult,
    _classify_recommendation,
)
from app.adaptive_intelligence import metrics as adaptive_metrics
from app.adaptive_intelligence.regime_adapter import RegimeAdapter
from app.adaptive_intelligence.risk_tuner import RiskTuner
from app.adaptive_intelligence.strategy_feedback import StrategyFeedbackEngine

logger = logging.getLogger(__name__)


# ── Fallback empty results ─────────────────────────────────────────────────────

def _empty_strategy(lookback_days: int) -> StrategyFeedbackResult:
    now = datetime.now(timezone.utc)
    return StrategyFeedbackResult(
        evaluated_at=now,
        lookback_days=lookback_days,
        total_outcomes=0,
        slices=[],
        summary={"BOOST": 0, "KEEP": 0, "THROTTLE": 0, "DISABLE": 0, "OBSERVE_ONLY": 0},
        top_performers=[],
        underperformers=[],
    )


def _empty_calibration() -> ConfidenceCalibrationResult:
    now = datetime.now(timezone.utc)
    return ConfidenceCalibrationResult(
        evaluated_at=now,
        total_outcomes=0,
        buckets=[],
        calibrated_threshold=None,
        overall_calibration_slope=None,
        well_calibrated=False,
        overconfidence_warning=False,
        underconfidence_warning=False,
        recommended_min_confidence=None,
    )


def _empty_regime() -> RegimeAdapterResult:
    now = datetime.now(timezone.utc)
    return RegimeAdapterResult(
        evaluated_at=now,
        adaptations=[],
        regimes_observed=[],
        dominant_regime=None,
        regime_distribution={},
        per_regime_performance={},
    )


def _empty_risk() -> RiskTuningResult:
    now = datetime.now(timezone.utc)
    return RiskTuningResult(
        evaluated_at=now,
        current_win_rate=None,
        current_expectancy=None,
        current_profit_factor=None,
        max_observed_drawdown_pct=None,
        suggested_position_size_multiplier=1.0,
        suggested_min_confidence=55,
        risk_level="MODERATE",
        throttle_recommended=False,
        disable_recommended=False,
        reasoning=["no data available — defaulting to MODERATE risk"],
        policy_hints={},
    )


# ── Overall recommendation logic ───────────────────────────────────────────────

def _derive_overall(
    strategy: StrategyFeedbackResult,
    calibration: ConfidenceCalibrationResult,
    risk: RiskTuningResult,
) -> tuple[Recommendation, str]:
    """Aggregate the three engine outputs into one advisory recommendation."""
    reasons: list[str] = []

    # Risk level → base recommendation
    if risk.risk_level == "CRITICAL":
        rec: Recommendation = "DISABLE"
        reasons.append("critical risk level")
    elif risk.risk_level == "HIGH":
        rec = "THROTTLE"
        reasons.append("high risk level")
    elif risk.disable_recommended:
        rec = "DISABLE"
        reasons.append("majority of slices recommend disable")
    elif risk.throttle_recommended:
        rec = "THROTTLE"
        reasons.append("majority of slices recommend throttle")
    else:
        rec = "KEEP"

    # BOOST only if explicitly warranted
    if (
        risk.risk_level == "LOW"
        and len(strategy.top_performers) > 0
        and calibration.well_calibrated
        and not calibration.overconfidence_warning
    ):
        rec = "BOOST"
        reasons.append(
            f"{len(strategy.top_performers)} top-performing slice(s) + well-calibrated model"
        )

    # Fall back to OBSERVE_ONLY if no real data
    if strategy.total_outcomes == 0:
        rec = "OBSERVE_ONLY"
        reasons.append("no outcomes in lookback window")

    summary = "; ".join(reasons) if reasons else "acceptable performance across all dimensions"
    return rec, summary


# ── Orchestrator ───────────────────────────────────────────────────────────────

class AdaptiveIntelligenceOrchestrator:
    """Run all Adaptive Intelligence engines and return a unified report.

    Parameters
    ----------
    db:
        Active SQLAlchemy Session.
    lookback_days:
        Calendar days of outcome history to include (default: 30).
    environment:
        Runtime environment label (e.g. "production", "staging").
    """

    def __init__(
        self,
        db: Session,
        lookback_days: int = 30,
        environment: str = "production",
    ) -> None:
        self._db = db
        self._lookback_days = lookback_days
        self._environment = environment

    # ------------------------------------------------------------------

    def evaluate(self) -> AdaptiveIntelligenceReport:
        t0 = time.perf_counter()

        # ── Strategy Feedback ─────────────────────────────────────────────────
        try:
            strategy = StrategyFeedbackEngine(self._db, self._lookback_days).evaluate()
        except Exception as exc:
            logger.exception("adaptive.orchestrator: strategy_feedback failed: %s", exc)
            strategy = _empty_strategy(self._lookback_days)

        # ── Confidence Calibration ────────────────────────────────────────────
        try:
            calibration = ConfidenceCalibrationEngine(self._db, self._lookback_days).evaluate()
        except Exception as exc:
            logger.exception("adaptive.orchestrator: confidence_calibration failed: %s", exc)
            calibration = _empty_calibration()

        # ── Regime Adapter ────────────────────────────────────────────────────
        try:
            regime = RegimeAdapter(self._db, self._lookback_days).evaluate()
        except Exception as exc:
            logger.exception("adaptive.orchestrator: regime_adapter failed: %s", exc)
            regime = _empty_regime()

        # ── Risk Tuner ────────────────────────────────────────────────────────
        try:
            risk = RiskTuner(self._db, self._lookback_days).evaluate(
                strategy=strategy,
                calibration=calibration,
                regime=regime,
            )
        except Exception as exc:
            logger.exception("adaptive.orchestrator: risk_tuner failed: %s", exc)
            risk = _empty_risk()

        # ── Overall recommendation ────────────────────────────────────────────
        overall_rec, overall_reasoning = _derive_overall(strategy, calibration, risk)

        # ── Merged policy hints ───────────────────────────────────────────────
        policy_hints: dict[str, Any] = {
            **risk.policy_hints,
            "overall_recommendation": overall_rec,
            "overall_reasoning": overall_reasoning,
            "calibrated_threshold": calibration.calibrated_threshold,
            "dominant_regime": regime.dominant_regime,
        }

        duration = time.perf_counter() - t0

        # ── Publish metrics best-effort ───────────────────────────────────────
        try:
            adaptive_metrics.publish_strategy_feedback(strategy)
            adaptive_metrics.publish_calibration(calibration)
            adaptive_metrics.publish_regime(regime)
            adaptive_metrics.publish_risk(risk)
            adaptive_metrics.intelligence_run_duration_seconds.observe(duration)
            adaptive_metrics.intelligence_runs_total.labels(status="success").inc()
        except Exception:
            pass

        report = AdaptiveIntelligenceReport(
            generated_at=datetime.now(timezone.utc),
            environment=self._environment,
            lookback_days=self._lookback_days,
            strategy_feedback=strategy,
            calibration=calibration,
            regime=regime,
            risk=risk,
            overall_recommendation=overall_rec,
            overall_reasoning=overall_reasoning,
            policy_hints=policy_hints,
        )

        logger.info(
            "adaptive.orchestrator: evaluation complete",
            extra={
                "duration_seconds": round(duration, 3),
                "overall_recommendation": overall_rec,
                "risk_level": risk.risk_level,
                "total_strategy_outcomes": strategy.total_outcomes,
                "total_calibration_outcomes": calibration.total_outcomes,
            },
        )

        return report
