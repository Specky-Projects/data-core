"""AdaptiveIntelligenceOrchestrator — runs all four engines in sequence.

Never breaks the trading runtime:
  - Each engine failure is caught and logged; a degraded result is returned.
  - Metrics are published best-effort (failures silently ignored).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.adaptive_intelligence import metrics as adaptive_metrics
from app.adaptive_intelligence.confidence_calibration import ConfidenceCalibrationEngine
from app.adaptive_intelligence.dto import (
    AdaptiveIntelligenceReport,
    ConfidenceCalibrationResult,
    ContinuousLearningProfile,
    ContinuousLearningSignal,
    EvaluationContext,
    Recommendation,
    RegimeAdapterResult,
    RiskTuningResult,
    ScientificVersionMetadata,
    StrategyFeedbackResult,
    build_decision_hash,
    build_feature_provenance,
)
from app.adaptive_intelligence.regime_adapter import RegimeAdapter
from app.adaptive_intelligence.risk_tuner import RiskTuner
from app.adaptive_intelligence.strategy_feedback import StrategyFeedbackEngine

logger = logging.getLogger(__name__)

_EPOCH = datetime.fromisoformat("1970-01-01T00:00:00+00:00")


def _fallback_context(lookback_days: int) -> EvaluationContext:
    return EvaluationContext(
        evaluation_timestamp=_EPOCH,
        replay_mode=True,
        dataset_timestamp=_EPOCH,
        dataset_version="dataset:empty",
        replay_configuration={"derived_from": "fallback"},
        lookback_days=lookback_days,
    )


# ── Fallback empty results ─────────────────────────────────────────────────────

def _empty_strategy(
    lookback_days: int,
    context: EvaluationContext | None = None,
) -> StrategyFeedbackResult:
    context = context or _fallback_context(lookback_days)
    return StrategyFeedbackResult(
        evaluated_at=context.evaluation_timestamp,
        lookback_days=lookback_days,
        total_outcomes=0,
        slices=[],
        summary={"BOOST": 0, "KEEP": 0, "THROTTLE": 0, "DISABLE": 0, "OBSERVE_ONLY": 0},
        top_performers=[],
        underperformers=[],
    )


def _empty_calibration(context: EvaluationContext | None = None) -> ConfidenceCalibrationResult:
    context = context or _fallback_context(30)
    return ConfidenceCalibrationResult(
        evaluated_at=context.evaluation_timestamp,
        total_outcomes=0,
        buckets=[],
        calibrated_threshold=None,
        overall_calibration_slope=None,
        well_calibrated=False,
        overconfidence_warning=False,
        underconfidence_warning=False,
        recommended_min_confidence=None,
        evaluation_context=context,
    )


def _empty_regime(context: EvaluationContext | None = None) -> RegimeAdapterResult:
    context = context or _fallback_context(30)
    return RegimeAdapterResult(
        evaluated_at=context.evaluation_timestamp,
        adaptations=[],
        regimes_observed=[],
        dominant_regime=None,
        regime_distribution={},
        per_regime_performance={},
    )


def _empty_risk(context: EvaluationContext | None = None) -> RiskTuningResult:
    context = context or _fallback_context(30)
    return RiskTuningResult(
        evaluated_at=context.evaluation_timestamp,
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


def _merge_learning_profile(
    strategy: StrategyFeedbackResult,
    calibration: ConfidenceCalibrationResult,
    lookback_days: int,
    context: EvaluationContext,
) -> ContinuousLearningProfile | None:
    profile = strategy.continuous_learning
    if profile is None and not calibration.buckets:
        return None

    decision_quality: list[ContinuousLearningSignal] = []
    for bucket in calibration.buckets:
        if bucket.learning_audit is None:
            continue
        decision_quality.append(ContinuousLearningSignal(
            dimension="decision_quality",
            entity_id=bucket.label,
            entity_type="confidence_bucket",
            current_confidence=bucket.reliability_score,
            uncertainty=round(1.0 - min(bucket.sample_size / 30.0, 1.0), 4),
            evidence_ids=bucket.evidence_ids,
            data_origin="trading_signal_outcomes",
            positive_factors=bucket.learning_audit.positive_factors,
            negative_factors=bucket.learning_audit.negative_factors,
            rationale=bucket.learning_audit.rationale,
            audit_trail=bucket.learning_audit,
        ))

    if profile is None:
        avg_decision = (
            sum(signal.current_confidence for signal in decision_quality) / len(decision_quality)
            if decision_quality
            else 0.0
        )
        coverage = min(calibration.total_outcomes / 100.0, 1.0)
        return ContinuousLearningProfile(
            evaluated_at=context.evaluation_timestamp,
            lookback_days=lookback_days,
            coverage_sample_size=calibration.total_outcomes,
            decision_quality=decision_quality,
            feedback={
                "historical_calibration": calibration.historical_calibration,
                "reinforcement_scoring": round(avg_decision, 4),
            },
            self_evaluation={
                "current_confidence": round(avg_decision, 4),
                "uncertainty": round(1.0 - coverage, 4),
                "evidence_count": calibration.total_outcomes,
                "justification": "Decision learning derived from confidence calibration buckets.",
                "score_change_reason": "calibration evidence adjusted decision-quality score",
            },
            observability={
                "confidence_evolution": round(avg_decision, 4),
                "precision_evolution": round(avg_decision, 4),
                "learning_rate": round(
                    len(decision_quality) / max(calibration.total_outcomes, 1),
                    4,
                ),
                "convergence_rate": round(coverage, 4),
                "drift": round(1.0 - avg_decision, 4),
                "stability": round(coverage, 4),
                "historical_coverage": round(coverage, 4),
            },
            evaluation_context=context,
            versions=ScientificVersionMetadata(),
        )

    profile.evaluated_at = context.evaluation_timestamp
    profile.evaluation_context = context
    profile.decision_quality = decision_quality
    profile.feedback["historical_calibration"] = calibration.historical_calibration
    if decision_quality:
        decision_score = sum(s.current_confidence for s in decision_quality) / len(decision_quality)
        profile.feedback["decision_reinforcement_scoring"] = round(decision_score, 4)
        profile.observability["precision_evolution"] = round(decision_score, 4)
        combined_confidence = (
            float(profile.self_evaluation.get("current_confidence", 0.0)) + decision_score
        ) / 2.0
        profile.self_evaluation["current_confidence"] = round(combined_confidence, 4)
        profile.self_evaluation["uncertainty"] = round(
            1.0 - min(profile.coverage_sample_size / 100.0, 1.0),
            4,
        )
        profile.self_evaluation["score_change_reason"] = (
            "source, discovery, decision and economic learning were recalibrated "
            "from the same historical evidence set"
        )
    return profile


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
        evaluation_context: EvaluationContext | None = None,
    ) -> None:
        self._db = db
        self._lookback_days = lookback_days
        self._environment = environment
        self._evaluation_context = evaluation_context

    # ------------------------------------------------------------------

    def evaluate(self) -> AdaptiveIntelligenceReport:
        t0 = time.perf_counter()
        context = self._evaluation_context or _fallback_context(self._lookback_days)
        versions = ScientificVersionMetadata()

        # ── Strategy Feedback ─────────────────────────────────────────────────
        try:
            strategy = StrategyFeedbackEngine(
                self._db,
                self._lookback_days,
                evaluation_context=self._evaluation_context,
            ).evaluate()
            if strategy.continuous_learning and strategy.continuous_learning.evaluation_context:
                context = strategy.continuous_learning.evaluation_context
        except Exception as exc:
            logger.exception("adaptive.orchestrator: strategy_feedback failed: %s", exc)
            strategy = _empty_strategy(self._lookback_days, context)

        # ── Confidence Calibration ────────────────────────────────────────────
        try:
            calibration = ConfidenceCalibrationEngine(
                self._db,
                self._lookback_days,
                evaluation_context=context,
            ).evaluate()
        except Exception as exc:
            logger.exception("adaptive.orchestrator: confidence_calibration failed: %s", exc)
            calibration = _empty_calibration(context)

        # ── Regime Adapter ────────────────────────────────────────────────────
        try:
            regime = RegimeAdapter(
                self._db,
                self._lookback_days,
                evaluation_context=context,
            ).evaluate()
        except Exception as exc:
            logger.exception("adaptive.orchestrator: regime_adapter failed: %s", exc)
            regime = _empty_regime(context)

        # ── Risk Tuner ────────────────────────────────────────────────────────
        try:
            risk = RiskTuner(
                self._db,
                self._lookback_days,
                evaluation_context=context,
            ).evaluate(
                strategy=strategy,
                calibration=calibration,
                regime=regime,
            )
        except Exception as exc:
            logger.exception("adaptive.orchestrator: risk_tuner failed: %s", exc)
            risk = _empty_risk(context)

        # ── Overall recommendation ────────────────────────────────────────────
        overall_rec, overall_reasoning = _derive_overall(strategy, calibration, risk)
        continuous_learning = _merge_learning_profile(
            strategy,
            calibration,
            self._lookback_days,
            context,
        )

        # ── Merged policy hints ───────────────────────────────────────────────
        policy_hints: dict[str, Any] = {
            **risk.policy_hints,
            "versions": versions.model_dump(mode="json"),
            "evaluation_context": context.model_dump(mode="json"),
            "overall_recommendation": overall_rec,
            "overall_reasoning": overall_reasoning,
            "calibrated_threshold": calibration.calibrated_threshold,
            "dominant_regime": regime.dominant_regime,
            "continuous_learning": (
                continuous_learning.model_dump(mode="json")
                if continuous_learning is not None
                else None
            ),
        }
        report_provenance = build_feature_provenance(
            evaluation_context=context,
            entity_id="adaptive_intelligence_report",
            features={
                "overall_recommendation": overall_rec,
                "overall_reasoning": overall_reasoning,
                "risk_level": risk.risk_level,
                "strategy_outcomes": strategy.total_outcomes,
                "calibration_outcomes": calibration.total_outcomes,
            },
            evidence_ids=(
                continuous_learning.self_evaluation.get("evidence_ids", [])
                if continuous_learning
                else []
            ),
            versions=versions,
        )
        report_hash = build_decision_hash(
            evaluation_context=context,
            versions=versions,
            provenance=report_provenance,
            entity_id="adaptive_intelligence_report",
            recommendation=overall_rec,
        )
        policy_hints["decision_hash"] = report_hash

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
            generated_at=context.evaluation_timestamp,
            environment=self._environment,
            lookback_days=self._lookback_days,
            strategy_feedback=strategy,
            calibration=calibration,
            regime=regime,
            risk=risk,
            overall_recommendation=overall_rec,
            overall_reasoning=overall_reasoning,
            policy_hints=policy_hints,
            continuous_learning=continuous_learning,
            evaluation_context=context,
            versions=versions,
            decision_hash=report_hash,
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
