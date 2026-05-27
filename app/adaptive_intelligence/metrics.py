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


def publish_strategy_feedback(result: "StrategyFeedbackResult") -> None:  # type: ignore[name-defined]  # noqa: F821
    """Update strategy feedback gauges from a completed StrategyFeedbackResult."""
    try:
        strategy_slices_total.set(len(result.slices))
        strategy_outcomes_analysed.set(result.total_outcomes)
        strategy_boost_total.set(result.summary.get("BOOST", 0))
        strategy_keep_total.set(result.summary.get("KEEP", 0))
        strategy_throttle_total.set(result.summary.get("THROTTLE", 0))
        strategy_disable_total.set(result.summary.get("DISABLE", 0))
        strategy_observe_only_total.set(result.summary.get("OBSERVE_ONLY", 0))
    except Exception:
        pass


def publish_calibration(result: "ConfidenceCalibrationResult") -> None:  # type: ignore[name-defined]  # noqa: F821
    """Update calibration gauges from a completed ConfidenceCalibrationResult."""
    try:
        calibration_well_calibrated.set(1 if result.well_calibrated else 0)
        calibration_overconfidence_warning.set(1 if result.overconfidence_warning else 0)
        calibration_underconfidence_warning.set(1 if result.underconfidence_warning else 0)
        calibration_threshold.set(result.calibrated_threshold if result.calibrated_threshold is not None else -1)
        calibration_slope.set(result.overall_calibration_slope if result.overall_calibration_slope is not None else 0.0)
        calibration_outcomes_analysed.set(result.total_outcomes)
    except Exception:
        pass


def publish_regime(result: "RegimeAdapterResult") -> None:  # type: ignore[name-defined]  # noqa: F821
    """Update regime gauges from a completed RegimeAdapterResult."""
    try:
        regime_adaptations_total.set(len(result.adaptations))
        if result.dominant_regime:
            regime_dominant.labels(regime=result.dominant_regime).set(1)
    except Exception:
        pass


def publish_risk(result: "RiskTuningResult") -> None:  # type: ignore[name-defined]  # noqa: F821
    """Update risk gauges from a completed RiskTuningResult."""
    try:
        risk_level_gauge.set(_RISK_ENCODING.get(result.risk_level, 0))
        risk_position_size_multiplier.set(result.suggested_position_size_multiplier)
        risk_min_confidence.set(result.suggested_min_confidence)
        risk_throttle_recommended.set(1 if result.throttle_recommended else 0)
        risk_disable_recommended.set(1 if result.disable_recommended else 0)
    except Exception:
        pass
