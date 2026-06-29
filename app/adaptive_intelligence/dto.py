"""DTOs for the Adaptive Intelligence Layer."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ── Recommendation enum ────────────────────────────────────────────────────────

Recommendation = Literal["KEEP", "THROTTLE", "DISABLE", "BOOST", "OBSERVE_ONLY"]

# Minimum samples required before any non-OBSERVE_ONLY recommendation.
MIN_SAMPLE_FOR_RECOMMENDATION = 10
MIN_SAMPLE_FOR_BOOST = 30
MIN_SAMPLE_FOR_DISABLE = 20

LEARNING_VERSION = "business-os-1.3-stage-3.6"
CALIBRATION_VERSION = "calibration-buckets-v1-stage-3.6"
FEATURE_VERSION = "adaptive-learning-features-v1-stage-3.6"
POLICY_VERSION = "adaptive-policy-hints-v1-stage-3.6"
ALGORITHM_VERSION = "deterministic-adaptive-learning-v1-stage-3.6"
RESEARCH_VERSION = "business-os-research-v1-stage-3.6"
EVIDENCE_VERSION = "trading-signal-outcomes-v1-stage-3.6"


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


class ScientificVersionMetadata(BaseModel):
    learning_version: str = LEARNING_VERSION
    calibration_version: str = CALIBRATION_VERSION
    feature_version: str = FEATURE_VERSION
    policy_version: str = POLICY_VERSION
    algorithm_version: str = ALGORITHM_VERSION
    research_version: str = RESEARCH_VERSION
    evidence_version: str = EVIDENCE_VERSION


class EvaluationContext(BaseModel):
    evaluation_timestamp: datetime
    replay_mode: bool = False
    dataset_timestamp: datetime | None = None
    dataset_version: str
    replay_configuration: dict[str, Any] = Field(default_factory=dict)
    lookback_days: int | None = None


class FeatureProvenance(BaseModel):
    dataset_version: str
    feature_snapshot_id: str
    feature_hash: str
    evidence_hash: str
    evidence_ids: list[str] = Field(default_factory=list)
    research_version: str = RESEARCH_VERSION
    policy_version: str = POLICY_VERSION


class ConfidenceEvolution(BaseModel):
    initial_confidence: float = Field(ge=0.0, le=1.0)
    calibrated_confidence: float = Field(ge=0.0, le=1.0)
    learned_confidence: float = Field(ge=0.0, le=1.0)
    final_confidence: float = Field(ge=0.0, le=1.0)
    initial_to_calibrated_delta: float
    calibrated_to_learned_delta: float
    learned_to_final_delta: float
    total_delta: float


class ScientificLineage(BaseModel):
    outcome: str
    evidence: str
    features: str
    calibration: str
    learning: str
    policy: str
    decision: str
    recommendation: str


class FeatureContribution(BaseModel):
    feature: str
    contribution: float
    normalized_contribution: float
    rank: int


class LongitudinalDriftMetric(BaseModel):
    window_days: int
    sample_size: int
    confidence: float
    stability: float
    volatility: float
    degradation: float
    improvement: float


class LearningSaturation(BaseModel):
    saturation_score: float = Field(ge=0.0, le=1.0)
    marginal_gain: float
    learning_velocity: float
    plateau_detected: bool


class ScientificLearningHealth(BaseModel):
    replay_readiness: float = Field(ge=0.0, le=1.0)
    version_completeness: float = Field(ge=0.0, le=1.0)
    evidence_quality: float = Field(ge=0.0, le=1.0)
    feature_provenance: float = Field(ge=0.0, le=1.0)
    learning_stability: float = Field(ge=0.0, le=1.0)
    calibration_quality: float = Field(ge=0.0, le=1.0)
    drift_stability: float = Field(ge=0.0, le=1.0)
    learning_saturation: float = Field(ge=0.0, le=1.0)
    explainability: float = Field(ge=0.0, le=1.0)
    audit_completeness: float = Field(ge=0.0, le=1.0)
    confidence_consistency: float = Field(ge=0.0, le=1.0)
    health_score: float = Field(ge=0.0, le=1.0)


def build_confidence_evolution(
    *,
    initial: float,
    calibrated: float,
    learned: float,
    final: float,
) -> ConfidenceEvolution:
    return ConfidenceEvolution(
        initial_confidence=round(initial, 4),
        calibrated_confidence=round(calibrated, 4),
        learned_confidence=round(learned, 4),
        final_confidence=round(final, 4),
        initial_to_calibrated_delta=round(calibrated - initial, 4),
        calibrated_to_learned_delta=round(learned - calibrated, 4),
        learned_to_final_delta=round(final - learned, 4),
        total_delta=round(final - initial, 4),
    )


def build_feature_provenance(
    *,
    evaluation_context: EvaluationContext,
    entity_id: str,
    features: dict[str, Any],
    evidence_ids: list[str],
    versions: ScientificVersionMetadata | None = None,
) -> FeatureProvenance:
    version_meta = versions or ScientificVersionMetadata()
    evidence_hash = stable_hash({"evidence_ids": sorted(evidence_ids)})
    feature_hash = stable_hash(
        {
            "entity_id": entity_id,
            "features": features,
            "dataset_version": evaluation_context.dataset_version,
            "versions": version_meta.model_dump(mode="json"),
        }
    )
    return FeatureProvenance(
        dataset_version=evaluation_context.dataset_version,
        feature_snapshot_id=stable_hash(
            {
                "entity_id": entity_id,
                "feature_hash": feature_hash,
                "evaluation_timestamp": evaluation_context.evaluation_timestamp,
            }
        ),
        feature_hash=feature_hash,
        evidence_hash=evidence_hash,
        evidence_ids=evidence_ids[:25],
        research_version=version_meta.research_version,
        policy_version=version_meta.policy_version,
    )


def build_feature_contributions(weights: dict[str, float]) -> list[FeatureContribution]:
    total = sum(abs(value) for value in weights.values()) or 1.0
    ranked = sorted(weights.items(), key=lambda item: (-abs(item[1]), item[0]))
    return [
        FeatureContribution(
            feature=name,
            contribution=round(value, 4),
            normalized_contribution=round(abs(value) / total, 4),
            rank=index + 1,
        )
        for index, (name, value) in enumerate(ranked)
    ]


def build_decision_hash(
    *,
    evaluation_context: EvaluationContext,
    versions: ScientificVersionMetadata,
    provenance: FeatureProvenance,
    entity_id: str,
    recommendation: str,
) -> str:
    return stable_hash(
        {
            "algorithm_version": versions.algorithm_version,
            "feature_hash": provenance.feature_hash,
            "dataset_version": evaluation_context.dataset_version,
            "policy_version": versions.policy_version,
            "evaluation_timestamp": evaluation_context.evaluation_timestamp,
            "learning_version": versions.learning_version,
            "entity_id": entity_id,
            "recommendation": recommendation,
        }
    )


def build_scientific_lineage(
    *,
    entity_id: str,
    evidence_hash: str,
    feature_hash: str,
    decision_hash: str,
    recommendation: str,
) -> ScientificLineage:
    return ScientificLineage(
        outcome="TradingSignalOutcome",
        evidence=evidence_hash,
        features=feature_hash,
        calibration=CALIBRATION_VERSION,
        learning=LEARNING_VERSION,
        policy=POLICY_VERSION,
        decision=decision_hash,
        recommendation=f"{entity_id}:{recommendation}",
    )


def _row_timestamp(row: Any) -> datetime | None:
    for attr in ("outcome_at", "evaluated_at", "signal_at"):
        value = getattr(row, attr, None)
        if isinstance(value, datetime):
            return value
    return None


def _row_signature(row: Any) -> dict[str, Any]:
    row_id = getattr(row, "id", None)
    return {
        "id": str(row_id) if row_id is not None else None,
        "symbol": getattr(row, "symbol", None),
        "timeframe": getattr(row, "timeframe", None),
        "signal": getattr(row, "signal", None),
        "confidence": getattr(row, "confidence", None),
        "regime": getattr(row, "regime", None),
        "price_change_pct": str(getattr(row, "price_change_pct", None)),
        "outcome_correct": getattr(row, "outcome_correct", None),
        "signal_at": getattr(row, "signal_at", None),
        "outcome_at": getattr(row, "outcome_at", None),
        "evaluated_at": getattr(row, "evaluated_at", None),
    }


def derive_evaluation_context(
    rows: list[Any],
    lookback_days: int,
    evaluation_context: EvaluationContext | None = None,
) -> EvaluationContext:
    if evaluation_context is not None:
        return evaluation_context.model_copy(
            update={"lookback_days": evaluation_context.lookback_days or lookback_days}
        )

    timestamps = [timestamp for row in rows if (timestamp := _row_timestamp(row)) is not None]
    evaluation_timestamp = (
        max(timestamps)
        if timestamps
        else datetime.fromisoformat("1970-01-01T00:00:00+00:00")
    )
    dataset_hash = stable_hash(
        {
            "lookback_days": lookback_days,
            "rows": sorted(
                (_row_signature(row) for row in rows),
                key=lambda item: stable_json(item),
            ),
        }
    )
    return EvaluationContext(
        evaluation_timestamp=evaluation_timestamp,
        replay_mode=True,
        dataset_timestamp=evaluation_timestamp,
        dataset_version=f"dataset:{dataset_hash[:16]}",
        replay_configuration={"derived_from": "TradingSignalOutcome", "row_count": len(rows)},
        lookback_days=lookback_days,
    )


def filter_rows_for_context(
    rows: list[Any],
    evaluation_context: EvaluationContext,
    lookback_days: int,
) -> list[Any]:
    cutoff = evaluation_context.evaluation_timestamp.timestamp() - (lookback_days * 86_400)
    end = evaluation_context.evaluation_timestamp.timestamp()
    filtered: list[Any] = []
    for row in rows:
        signal_at = getattr(row, "signal_at", None)
        if not isinstance(signal_at, datetime):
            continue
        ts = signal_at.timestamp()
        if cutoff <= ts <= end:
            filtered.append(row)
    return filtered


def compute_longitudinal_drift(
    rows: list[Any],
    evaluation_context: EvaluationContext,
) -> list[LongitudinalDriftMetric]:
    metrics: list[LongitudinalDriftMetric] = []
    for window_days in (7, 30, 90, 180, 365):
        window_rows = filter_rows_for_context(rows, evaluation_context, window_days)
        n = len(window_rows)
        if n == 0:
            confidence = stability = volatility = degradation = improvement = 0.0
        else:
            wins = sum(1 for row in window_rows if bool(getattr(row, "outcome_correct", False)))
            returns = [
                float(getattr(row, "price_change_pct", 0.0) or 0.0)
                for row in window_rows
            ]
            confidence = wins / n
            mean_return = sum(returns) / n
            variance = sum((ret - mean_return) ** 2 for ret in returns) / n
            volatility = min(1.0, variance ** 0.5 / 10.0)
            stability = max(0.0, 1.0 - volatility)
            degradation = max(0.0, 0.5 - confidence)
            improvement = max(0.0, confidence - 0.5)
        metrics.append(LongitudinalDriftMetric(
            window_days=window_days,
            sample_size=n,
            confidence=round(confidence, 4),
            stability=round(stability, 4),
            volatility=round(volatility, 4),
            degradation=round(degradation, 4),
            improvement=round(improvement, 4),
        ))
    return metrics


def compute_learning_saturation(drift: list[LongitudinalDriftMetric]) -> LearningSaturation:
    populated = [item for item in drift if item.sample_size > 0]
    if len(populated) < 2:
        return LearningSaturation(
            saturation_score=0.0,
            marginal_gain=0.0,
            learning_velocity=0.0,
            plateau_detected=False,
        )
    short = populated[0].confidence
    long = populated[-1].confidence
    marginal_gain = short - long
    learning_velocity = marginal_gain / max(populated[-1].window_days - populated[0].window_days, 1)
    saturation_score = max(0.0, min(1.0, 1.0 - abs(marginal_gain)))
    return LearningSaturation(
        saturation_score=round(saturation_score, 4),
        marginal_gain=round(marginal_gain, 4),
        learning_velocity=round(learning_velocity, 6),
        plateau_detected=abs(marginal_gain) < 0.02,
    )


def compute_freshness(
    rows: list[Any],
    evaluation_context: EvaluationContext,
) -> dict[str, float]:
    """Derive deterministic freshness scores from evaluation_context and row timestamps.

    All scores are in [0, 1] where 1 = perfectly fresh.
    Uses evaluation_timestamp as the reference — wall-clock independent.
    """
    ref_ts = evaluation_context.evaluation_timestamp.timestamp()
    if not rows:
        return {
            "dataset_freshness": 0.0,
            "evidence_freshness": 0.0,
            "feature_freshness": 0.0,
            "learning_freshness": 0.0,
        }

    timestamps = [_row_timestamp(row) for row in rows]
    valid_ts = [t.timestamp() for t in timestamps if t is not None]
    if not valid_ts:
        return {
            "dataset_freshness": 0.0,
            "evidence_freshness": 0.0,
            "feature_freshness": 0.0,
            "learning_freshness": 0.0,
        }

    newest_ts = max(valid_ts)
    oldest_ts = min(valid_ts)
    # Age of the newest evidence in days
    age_days = max((ref_ts - newest_ts) / 86_400.0, 0.0)
    # Span of evidence in days
    span_days = max((newest_ts - oldest_ts) / 86_400.0, 0.0)

    # Dataset freshness: decays over 30 days from the reference point
    dataset_freshness = max(0.0, min(1.0, 1.0 - age_days / 30.0))
    # Evidence freshness: 1 if newest evidence is within 7 days
    evidence_freshness = max(0.0, min(1.0, 1.0 - age_days / 7.0))
    # Feature freshness: proportional to row density (span vs lookback)
    lookback = float(evaluation_context.lookback_days or 30)
    feature_freshness = max(0.0, min(1.0, span_days / lookback)) if lookback > 0 else 0.0
    # Learning freshness: combination of evidence and feature freshness
    learning_freshness = round((dataset_freshness + evidence_freshness) / 2.0, 4)

    return {
        "dataset_freshness": round(dataset_freshness, 4),
        "evidence_freshness": round(evidence_freshness, 4),
        "feature_freshness": round(feature_freshness, 4),
        "learning_freshness": round(learning_freshness, 4),
    }


def compute_scientific_health(
    *,
    evaluation_context: EvaluationContext,
    versions: ScientificVersionMetadata,
    evidence_ids: list[str],
    drift: list[LongitudinalDriftMetric],
    saturation: LearningSaturation,
    explainability_present: bool,
    calibration_quality: float,
    confidence_consistency: float,
    feature_provenance_score: float = 1.0,
) -> ScientificLearningHealth:
    version_values = versions.model_dump(mode="json")
    version_completeness = (
        sum(1 for value in version_values.values() if value) / len(version_values)
    )
    evidence_quality = min(1.0, len(evidence_ids) / 10.0) if evidence_ids else 0.0
    drift_stability = (
        sum(item.stability for item in drift) / len(drift)
        if drift
        else 0.0
    )
    dimensions = {
        "replay_readiness": 1.0 if evaluation_context.replay_mode else 0.5,
        "version_completeness": version_completeness,
        "evidence_quality": evidence_quality,
        "feature_provenance": feature_provenance_score,
        "learning_stability": drift_stability,
        "calibration_quality": calibration_quality,
        "drift_stability": drift_stability,
        "learning_saturation": saturation.saturation_score,
        "explainability": 1.0 if explainability_present else 0.0,
        "audit_completeness": 1.0 if evidence_ids and explainability_present else 0.5,
        "confidence_consistency": confidence_consistency,
    }
    health_score = sum(dimensions.values()) / len(dimensions)
    return ScientificLearningHealth(
        **{key: round(value, 4) for key, value in dimensions.items()},
        health_score=round(health_score, 4),
    )


class LearningAuditTrail(BaseModel):
    """Explainable score movement for one adaptive learning update."""

    evidence_ids: list[str] = Field(default_factory=list)
    data_origin: str
    previous_score: float
    current_score: float
    score_delta: float
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)
    rationale: str
    lineage: list[str] = Field(default_factory=list)
    causal_history: list[str] = Field(default_factory=list)
    score_change_reason: str
    timestamp: datetime | None = None
    originating_components: list[str] = Field(default_factory=list)
    historical_references: list[str] = Field(default_factory=list)
    confidence_delta: float = 0.0
    versions: ScientificVersionMetadata = Field(default_factory=ScientificVersionMetadata)
    provenance: FeatureProvenance | None = None
    decision_hash: str | None = None
    scientific_lineage: ScientificLineage | None = None
    confidence_evolution: ConfidenceEvolution | None = None
    feature_importance: list[FeatureContribution] = Field(default_factory=list)


class ContinuousLearningSignal(BaseModel):
    """Reusable explainability envelope for adaptive learning dimensions."""

    dimension: str
    entity_id: str
    entity_type: str
    current_confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    data_origin: str
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)
    rationale: str
    audit_trail: LearningAuditTrail
    versions: ScientificVersionMetadata = Field(default_factory=ScientificVersionMetadata)
    provenance: FeatureProvenance | None = None
    decision_hash: str | None = None
    scientific_lineage: ScientificLineage | None = None
    confidence_evolution: ConfidenceEvolution | None = None
    feature_importance: list[FeatureContribution] = Field(default_factory=list)


class ContinuousLearningProfile(BaseModel):
    """Top-level adaptive learning profile derived from historical outcomes."""

    evaluated_at: datetime
    lookback_days: int
    coverage_sample_size: int
    source_quality: list[ContinuousLearningSignal] = Field(default_factory=list)
    discovery_quality: list[ContinuousLearningSignal] = Field(default_factory=list)
    decision_quality: list[ContinuousLearningSignal] = Field(default_factory=list)
    economic_learning: list[ContinuousLearningSignal] = Field(default_factory=list)
    feedback: dict[str, Any] = Field(default_factory=dict)
    self_evaluation: dict[str, Any] = Field(default_factory=dict)
    observability: dict[str, float] = Field(default_factory=dict)
    evaluation_context: EvaluationContext | None = None
    versions: ScientificVersionMetadata = Field(default_factory=ScientificVersionMetadata)
    decision_hash: str | None = None
    longitudinal_drift: list[LongitudinalDriftMetric] = Field(default_factory=list)
    learning_saturation: LearningSaturation | None = None
    scientific_health: ScientificLearningHealth | None = None
    freshness: dict[str, float] = Field(default_factory=dict)


def _classify_recommendation(
    win_rate: float,
    expectancy: float,
    profit_factor: float | None,
    sample_size: int,
) -> Recommendation:
    if sample_size < MIN_SAMPLE_FOR_RECOMMENDATION:
        return "OBSERVE_ONLY"
    pf = profit_factor or 0.0
    if win_rate >= 0.60 and expectancy > 0 and pf >= 1.5 and sample_size >= MIN_SAMPLE_FOR_BOOST:
        return "BOOST"
    if win_rate >= 0.50 and expectancy >= 0:
        return "KEEP"
    if win_rate < 0.40 and expectancy < -0.1 and sample_size >= MIN_SAMPLE_FOR_DISABLE:
        return "DISABLE"
    return "THROTTLE"


# ── Strategy Feedback ──────────────────────────────────────────────────────────

class StrategySlice(BaseModel):
    """Performance metrics for one (symbol, timeframe, regime, signal) slice."""
    symbol: str
    timeframe: str
    regime: str | None
    signal: str  # BUY | SELL
    sample_size: int
    win_rate: float = Field(ge=0.0, le=1.0)
    avg_return_pct: float
    expectancy: float      # win_rate * avg_win - loss_rate * avg_loss
    max_drawdown_pct: float
    profit_factor: float | None  # gross_profit / gross_loss; None if no losses
    avg_mfe_pct: float | None   # mean Maximum Favorable Excursion
    avg_mae_pct: float | None   # mean Maximum Adverse Excursion
    recommendation: Recommendation
    recommendation_reason: str
    priority_score: float = 0.0
    novelty_score: float = 0.0
    duplicate_risk: float = 0.0
    impact_score: float = 0.0
    relevance_score: float = 0.0
    accepted_opportunities: int = 0
    discarded_opportunities: int = 0
    time_to_validation_days: float | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    learning_audit: LearningAuditTrail | None = None
    versions: ScientificVersionMetadata = Field(default_factory=ScientificVersionMetadata)
    provenance: FeatureProvenance | None = None
    decision_hash: str | None = None
    scientific_lineage: ScientificLineage | None = None
    confidence_evolution: ConfidenceEvolution | None = None
    feature_importance: list[FeatureContribution] = Field(default_factory=list)


class StrategyFeedbackResult(BaseModel):
    evaluated_at: datetime
    lookback_days: int
    total_outcomes: int
    slices: list[StrategySlice]
    summary: dict[str, int]   # {KEEP: N, THROTTLE: N, ...}
    top_performers: list[str]   # slice keys worth boosting
    underperformers: list[str]  # slice keys needing throttle/disable
    continuous_learning: ContinuousLearningProfile | None = None


# ── Confidence Calibration ─────────────────────────────────────────────────────

class CalibrationBucket(BaseModel):
    """One confidence bucket (e.g. 61-80)."""
    label: str
    lower: int
    upper: int
    sample_size: int
    predicted_confidence_avg: float   # mean confidence score in this bucket
    realized_win_rate: float          # fraction of outcomes that were correct
    calibration_gap: float            # realized_win_rate - predicted_confidence_avg/100
    avg_return_pct: float
    overconfident: bool               # predicted >> realized
    underconfident: bool              # predicted << realized
    historical_accuracy: float = 0.0
    false_positive_rate: float = 0.0
    temporal_quality: float = 0.0
    stability_score: float = 0.0
    reliability_score: float = 0.0
    confidence_evolution_score: float = 0.0
    adaptive_weight: float = 1.0
    temporal_decay: float = 1.0
    evidence_ids: list[str] = Field(default_factory=list)
    learning_audit: LearningAuditTrail | None = None
    versions: ScientificVersionMetadata = Field(default_factory=ScientificVersionMetadata)
    provenance: FeatureProvenance | None = None
    decision_hash: str | None = None
    scientific_lineage: ScientificLineage | None = None
    confidence_evolution: ConfidenceEvolution | None = None
    feature_importance: list[FeatureContribution] = Field(default_factory=list)


class ConfidenceCalibrationResult(BaseModel):
    evaluated_at: datetime
    total_outcomes: int
    buckets: list[CalibrationBucket]
    calibrated_threshold: int | None  # lowest confidence where win_rate >= 55 %
    overall_calibration_slope: float | None  # positive = well calibrated
    well_calibrated: bool
    overconfidence_warning: bool
    underconfidence_warning: bool
    recommended_min_confidence: int | None
    historical_calibration: dict[str, Any] = Field(default_factory=dict)
    evaluation_context: EvaluationContext | None = None
    versions: ScientificVersionMetadata = Field(default_factory=ScientificVersionMetadata)


# ── Regime Adapter ─────────────────────────────────────────────────────────────

class RegimeAdaptation(BaseModel):
    regime: str
    signal: str          # BUY | SELL
    symbol: str | None   # None = applies to all symbols
    timeframe: str | None
    sample_size: int
    win_rate: float
    expectancy: float
    recommendation: Recommendation
    reason: str


class RegimeAdapterResult(BaseModel):
    evaluated_at: datetime
    adaptations: list[RegimeAdaptation]
    regimes_observed: list[str]
    dominant_regime: str | None
    regime_distribution: dict[str, int]   # regime → count
    per_regime_performance: dict[str, dict[str, Any]]


# ── Risk Tuner ────────────────────────────────────────────────────────────────

class RiskTuningResult(BaseModel):
    evaluated_at: datetime
    current_win_rate: float | None
    current_expectancy: float | None
    current_profit_factor: float | None
    max_observed_drawdown_pct: float | None
    suggested_position_size_multiplier: float  # 0.25 - 1.0 - 1.5
    suggested_min_confidence: int              # threshold hint
    risk_level: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
    throttle_recommended: bool
    disable_recommended: bool
    reasoning: list[str]
    policy_hints: dict[str, Any]  # structured hints for PolicyContract generator


# ── Top-level orchestrated report ─────────────────────────────────────────────

class AdaptiveIntelligenceReport(BaseModel):
    generated_at: datetime
    environment: str
    lookback_days: int
    strategy_feedback: StrategyFeedbackResult
    calibration: ConfidenceCalibrationResult
    regime: RegimeAdapterResult
    risk: RiskTuningResult
    # Aggregate advisory signal
    overall_recommendation: Recommendation
    overall_reasoning: str
    policy_hints: dict[str, Any]  # merged hints for downstream consumption
    continuous_learning: ContinuousLearningProfile | None = None
    evaluation_context: EvaluationContext | None = None
    versions: ScientificVersionMetadata = Field(default_factory=ScientificVersionMetadata)
    decision_hash: str | None = None

    def to_summary(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "overall_recommendation": self.overall_recommendation,
            "overall_reasoning": self.overall_reasoning,
            "risk_level": self.risk.risk_level,
            "suggested_min_confidence": self.risk.suggested_min_confidence,
            "suggested_position_size_multiplier": self.risk.suggested_position_size_multiplier,
            "well_calibrated": self.calibration.well_calibrated,
            "dominant_regime": self.regime.dominant_regime,
            "learning_confidence": (
                self.continuous_learning.self_evaluation.get("current_confidence")
                if self.continuous_learning
                else None
            ),
            "learning_uncertainty": (
                self.continuous_learning.self_evaluation.get("uncertainty")
                if self.continuous_learning
                else None
            ),
            "decision_hash": self.decision_hash,
            "learning_version": self.versions.learning_version,
            "algorithm_version": self.versions.algorithm_version,
            "dataset_version": (
                self.evaluation_context.dataset_version if self.evaluation_context else None
            ),
            "policy_hints": self.policy_hints,
        }
