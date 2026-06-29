"""Adaptive Intelligence Layer — Prometheus metrics.

All metrics use the prefix ``adaptive_`` to avoid collisions with
``optruth_`` and ``enforcement_`` metrics already registered in this process.

Best-effort: publish functions never raise.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── Strategy Feedback ──────────────────────────────────────────────────────────

strategy_slices_total = Gauge(
    "adaptive_strategy_slices_total",
    "Total number of (symbol, timeframe, regime, signal) slices evaluated",
)

strategy_boost_total = Gauge(
    "adaptive_strategy_boost_total",
    "Number of slices with BOOST recommendation",
)

strategy_keep_total = Gauge(
    "adaptive_strategy_keep_total",
    "Number of slices with KEEP recommendation",
)

strategy_throttle_total = Gauge(
    "adaptive_strategy_throttle_total",
    "Number of slices with THROTTLE recommendation",
)

strategy_disable_total = Gauge(
    "adaptive_strategy_disable_total",
    "Number of slices with DISABLE recommendation",
)

strategy_observe_only_total = Gauge(
    "adaptive_strategy_observe_only_total",
    "Number of slices with OBSERVE_ONLY recommendation (insufficient samples)",
)

strategy_outcomes_analysed = Gauge(
    "adaptive_strategy_outcomes_analysed",
    "Total signal outcomes included in the latest strategy feedback run",
)

# ── Confidence Calibration ─────────────────────────────────────────────────────

calibration_well_calibrated = Gauge(
    "adaptive_calibration_well_calibrated",
    "1 if confidence scores are well-calibrated (slope > 0 + no extreme gaps), 0 otherwise",
)

calibration_overconfidence_warning = Gauge(
    "adaptive_calibration_overconfidence_warning",
    "1 if overconfidence is detected across buckets, 0 otherwise",
)

calibration_underconfidence_warning = Gauge(
    "adaptive_calibration_underconfidence_warning",
    "1 if underconfidence is detected across buckets, 0 otherwise",
)

calibration_threshold = Gauge(
    "adaptive_calibration_threshold",
    "Lowest confidence bucket lower bound where win_rate >= 55 % (-1 if undetermined)",
)

calibration_slope = Gauge(
    "adaptive_calibration_slope",
    "Overall calibration slope (positive = well-calibrated, negative = reversed)",
)

calibration_outcomes_analysed = Gauge(
    "adaptive_calibration_outcomes_analysed",
    "Total signal outcomes included in the latest calibration run",
)

learning_confidence_evolution = Gauge(
    "adaptive_learning_confidence_evolution",
    "Current adaptive learning confidence evolution score by dimension",
    ["dimension"],
)

learning_precision_evolution = Gauge(
    "adaptive_learning_precision_evolution",
    "Historical precision/reliability score by learning dimension",
    ["dimension"],
)

learning_source_quality = Gauge(
    "adaptive_learning_source_quality",
    "Source quality score inferred from historical outcomes",
    ["source"],
)

learning_category_quality = Gauge(
    "adaptive_learning_category_quality",
    "Category quality score inferred from historical outcomes",
    ["category"],
)

learning_decision_quality = Gauge(
    "adaptive_learning_decision_quality",
    "Decision quality score by calibration bucket",
    ["bucket"],
)

learning_rate = Gauge(
    "adaptive_learning_rate",
    "Rate of adaptive learning signals generated per historical sample",
)

learning_convergence_rate = Gauge(
    "adaptive_learning_convergence_rate",
    "Historical coverage confidence used as convergence proxy",
)

learning_drift = Gauge(
    "adaptive_learning_drift",
    "Adaptive learning drift proxy: 1 - current confidence",
)

learning_stability = Gauge(
    "adaptive_learning_stability",
    "Adaptive learning stability proxy from coverage and return variance",
)

learning_historical_coverage = Gauge(
    "adaptive_learning_historical_coverage",
    "Coverage score for historical learning evidence",
)

learning_health_dimension = Gauge(
    "adaptive_learning_health_dimension",
    "Scientific learning health dimension score",
    ["dimension"],
)

learning_health_score = Gauge(
    "adaptive_learning_health_score",
    "Composite scientific learning health score",
)

learning_drift_window = Gauge(
    "adaptive_learning_drift_window",
    "Longitudinal drift score by deterministic window",
    ["window_days", "dimension"],
)

learning_saturation_score = Gauge(
    "adaptive_learning_saturation_score",
    "Learning saturation score from deterministic longitudinal windows",
)

learning_marginal_gain = Gauge(
    "adaptive_learning_marginal_gain",
    "Marginal confidence gain between short and long deterministic windows",
)

learning_version_info = Gauge(
    "adaptive_learning_version_info",
    "Info gauge carrying immutable scientific learning versions",
    [
        "learning_version",
        "calibration_version",
        "feature_version",
        "policy_version",
        "algorithm_version",
        "research_version",
        "evidence_version",
    ],
)

# ── Regime Adapter ─────────────────────────────────────────────────────────────

regime_adaptations_total = Gauge(
    "adaptive_regime_adaptations_total",
    "Total number of regime×signal×symbol adaptations produced",
)

regime_dominant = Gauge(
    "adaptive_regime_dominant_info",
    "Info gauge: always 1; label carries the dominant regime name",
    ["regime"],
)

# ── Risk Tuner ─────────────────────────────────────────────────────────────────

risk_level_gauge = Gauge(
    "adaptive_risk_level",
    "Risk level encoded: 4=LOW 3=MODERATE 2=HIGH 1=CRITICAL",
)

risk_position_size_multiplier = Gauge(
    "adaptive_risk_position_size_multiplier",
    "Suggested position size multiplier from risk tuner (0.25 – 1.5)",
)

risk_min_confidence = Gauge(
    "adaptive_risk_min_confidence",
    "Suggested minimum confidence threshold from risk tuner (0-100)",
)

risk_throttle_recommended = Gauge(
    "adaptive_risk_throttle_recommended",
    "1 if risk tuner recommends throttle, 0 otherwise",
)

risk_disable_recommended = Gauge(
    "adaptive_risk_disable_recommended",
    "1 if risk tuner recommends full disable, 0 otherwise",
)

# ── Evaluation counters ────────────────────────────────────────────────────────

intelligence_runs_total = Counter(
    "adaptive_intelligence_runs_total",
    "Total number of full AdaptiveIntelligence orchestration runs",
    ["status"],  # success | error
)

intelligence_run_duration_seconds = Histogram(
    "adaptive_intelligence_run_duration_seconds",
    "Wall-clock duration of a full AdaptiveIntelligence evaluation",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)


# ── Publish helpers ────────────────────────────────────────────────────────────

_RISK_ENCODING = {"LOW": 4, "MODERATE": 3, "HIGH": 2, "CRITICAL": 1}


def publish_strategy_feedback(result: StrategyFeedbackResult) -> None:  # type: ignore[name-defined]  # noqa: F821
    """Update strategy feedback gauges from a completed StrategyFeedbackResult."""
    try:
        strategy_slices_total.set(len(result.slices))
        strategy_outcomes_analysed.set(result.total_outcomes)
        strategy_boost_total.set(result.summary.get("BOOST", 0))
        strategy_keep_total.set(result.summary.get("KEEP", 0))
        strategy_throttle_total.set(result.summary.get("THROTTLE", 0))
        strategy_disable_total.set(result.summary.get("DISABLE", 0))
        strategy_observe_only_total.set(result.summary.get("OBSERVE_ONLY", 0))
        if result.continuous_learning:
            profile = result.continuous_learning
            learning_version_info.labels(
                learning_version=profile.versions.learning_version,
                calibration_version=profile.versions.calibration_version,
                feature_version=profile.versions.feature_version,
                policy_version=profile.versions.policy_version,
                algorithm_version=profile.versions.algorithm_version,
                research_version=profile.versions.research_version,
                evidence_version=profile.versions.evidence_version,
            ).set(1)
            for signal in profile.source_quality:
                learning_source_quality.labels(source=signal.entity_id).set(signal.current_confidence)
            for signal in profile.discovery_quality:
                category = signal.entity_id.split("|")[2] if "|" in signal.entity_id else "unknown"
                learning_category_quality.labels(category=category).set(signal.current_confidence)
            for key, value in profile.observability.items():
                if key == "learning_rate":
                    learning_rate.set(value)
                elif key == "convergence_rate":
                    learning_convergence_rate.set(value)
                elif key == "drift":
                    learning_drift.set(value)
                elif key == "stability":
                    learning_stability.set(value)
                elif key == "historical_coverage":
                    learning_historical_coverage.set(value)
            current = float(profile.self_evaluation.get("current_confidence", 0.0))
            learning_confidence_evolution.labels(dimension="continuous_learning").set(current)
            learning_precision_evolution.labels(dimension="discovery_quality").set(current)
            for drift in profile.longitudinal_drift:
                window = str(drift.window_days)
                learning_drift_window.labels(window_days=window, dimension="stability").set(
                    drift.stability
                )
                learning_drift_window.labels(window_days=window, dimension="volatility").set(
                    drift.volatility
                )
                learning_drift_window.labels(window_days=window, dimension="degradation").set(
                    drift.degradation
                )
                learning_drift_window.labels(window_days=window, dimension="improvement").set(
                    drift.improvement
                )
            if profile.learning_saturation:
                learning_saturation_score.set(profile.learning_saturation.saturation_score)
                learning_marginal_gain.set(profile.learning_saturation.marginal_gain)
            if profile.scientific_health:
                health = profile.scientific_health
                learning_health_score.set(health.health_score)
                for dimension, value in health.model_dump(mode="json").items():
                    if dimension != "health_score":
                        learning_health_dimension.labels(dimension=dimension).set(value)
    except Exception:
        pass


def publish_calibration(result: ConfidenceCalibrationResult) -> None:  # type: ignore[name-defined]  # noqa: F821
    """Update calibration gauges from a completed ConfidenceCalibrationResult."""
    try:
        calibration_well_calibrated.set(1 if result.well_calibrated else 0)
        calibration_overconfidence_warning.set(1 if result.overconfidence_warning else 0)
        calibration_underconfidence_warning.set(1 if result.underconfidence_warning else 0)
        calibration_threshold.set(
            result.calibrated_threshold if result.calibrated_threshold is not None else -1
        )
        calibration_slope.set(
            result.overall_calibration_slope
            if result.overall_calibration_slope is not None
            else 0.0
        )
        calibration_outcomes_analysed.set(result.total_outcomes)
        for bucket in result.buckets:
            learning_decision_quality.labels(bucket=bucket.label).set(bucket.reliability_score)
        if result.historical_calibration:
            learning_precision_evolution.labels(dimension="decision_quality").set(
                float(result.historical_calibration.get("decision_quality_score", 0.0))
            )
    except Exception:
        pass


def publish_regime(result: RegimeAdapterResult) -> None:  # type: ignore[name-defined]  # noqa: F821
    """Update regime gauges from a completed RegimeAdapterResult."""
    try:
        regime_adaptations_total.set(len(result.adaptations))
        if result.dominant_regime:
            regime_dominant.labels(regime=result.dominant_regime).set(1)
    except Exception:
        pass


def publish_risk(result: RiskTuningResult) -> None:  # type: ignore[name-defined]  # noqa: F821
    """Update risk gauges from a completed RiskTuningResult."""
    try:
        risk_level_gauge.set(_RISK_ENCODING.get(result.risk_level, 0))
        risk_position_size_multiplier.set(result.suggested_position_size_multiplier)
        risk_min_confidence.set(result.suggested_min_confidence)
        risk_throttle_recommended.set(1 if result.throttle_recommended else 0)
        risk_disable_recommended.set(1 if result.disable_recommended else 0)
    except Exception:
        pass
