"""Operational Truth Layer — Prometheus metrics.

All metrics use the prefix ``optruth_`` to avoid collisions with existing
metric files (api/metrics.py, api/runtime_metrics.py, api/live_metrics.py).
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── Scores (0-100) ─────────────────────────────────────────────────────────────

operational_confidence_score = Gauge(
    "optruth_operational_confidence_score",
    "Weighted operational confidence score across all subsystems (0-100)",
)

runtime_truth_score = Gauge(
    "optruth_runtime_truth_score",
    "Runtime subsystem truth score: scheduler + worker + queue health (0-100)",
)

dataset_truth_score = Gauge(
    "optruth_dataset_truth_score",
    "Dataset truth score: freshness + integrity + lag (0-100)",
)

replayability_score = Gauge(
    "optruth_replayability_score",
    "Replayability score: replay gaps + sequence continuity (0-100)",
)

determinism_score = Gauge(
    "optruth_determinism_score",
    "Determinism score: deterministic replay fidelity (0-100)",
)

quant_reliability_score = Gauge(
    "optruth_quant_reliability_score",
    "Quantitative reliability score: signal stability + calibration + entropy (0-100)",
)

infra_score = Gauge(
    "optruth_infra_score",
    "Infrastructure score: postgres + redis + network (0-100)",
)

security_score = Gauge(
    "optruth_security_score",
    "Security posture score: auth + secrets + dry_run (0-100)",
)

# ── Pressure gauges ────────────────────────────────────────────────────────────

queue_pressure_score = Gauge(
    "optruth_queue_pressure_score",
    "Queue backlog pressure score (0-100, higher = worse)",
)

dataset_drift_score = Gauge(
    "optruth_dataset_drift_score",
    "Dataset schema/lineage drift score (0-100, higher = more drift)",
)

# ── Status enum metric ─────────────────────────────────────────────────────────

operational_status_gauge = Gauge(
    "optruth_operational_status",
    "Operational status encoded: 5=HEALTHY 4=DEGRADED 3=PARTIALLY_UNSAFE 2=UNSAFE 1=CRITICAL",
)

safe_mode_active = Gauge(
    "optruth_safe_mode_active",
    "1 if safe mode is currently active, 0 otherwise",
)

degradation_detected = Gauge(
    "optruth_degradation_detected",
    "1 if operational degradation has been detected, 0 otherwise",
)

# ── Counters ───────────────────────────────────────────────────────────────────

runtime_degradation_total = Counter(
    "optruth_runtime_degradation_total",
    "Total number of runtime degradation events detected",
    ["severity"],  # warning | critical
)

safe_mode_activations_total = Counter(
    "optruth_safe_mode_activations_total",
    "Total number of times safe mode was activated",
)

scheduler_stale_total = Counter(
    "optruth_scheduler_stale_total",
    "Total number of scheduler stale detections",
)

replay_gap_total = Counter(
    "optruth_replay_gap_total",
    "Total number of replay sequence gaps detected",
)

# ── Ratios ─────────────────────────────────────────────────────────────────────

invalid_decision_ratio = Gauge(
    "optruth_invalid_decision_ratio",
    "Ratio of invalid decisions in the quant analysis window (0.0 - 1.0)",
)

# ── Staleness ─────────────────────────────────────────────────────────────────

scheduler_heartbeat_age_seconds_gauge = Gauge(
    "optruth_scheduler_heartbeat_age_seconds",
    "Seconds since the scheduler last wrote a heartbeat",
)

dataset_latest_age_seconds = Gauge(
    "optruth_dataset_latest_age_seconds",
    "Age in seconds of the most recent crypto raw record",
    ["module"],
)

replayability_age_seconds = Gauge(
    "optruth_replayability_age_seconds",
    "Age in seconds of the most recent replay-eligible snapshot",
)

# ── Evaluation duration ────────────────────────────────────────────────────────

evaluation_duration_seconds = Histogram(
    "optruth_evaluation_duration_seconds",
    "Wall-clock duration of a full ProductionReadiness evaluation",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)


# ── Helper ─────────────────────────────────────────────────────────────────────

_STATUS_ENCODING = {
    "HEALTHY": 5,
    "DEGRADED": 4,
    "PARTIALLY_UNSAFE": 3,
    "UNSAFE": 2,
    "CRITICAL": 1,
}


def publish_report(report: "ProductionReadinessReport") -> None:  # type: ignore[name-defined]  # noqa: F821
    """Push all gauge/counter updates from a completed report."""
    operational_confidence_score.set(report.operational_confidence_score)
    runtime_truth_score.set(report.runtime_score)
    dataset_truth_score.set(report.dataset_score)
    replayability_score.set(report.replayability_score)
    determinism_score.set(report.replayability.determinism_score)
    quant_reliability_score.set(report.quant_reliability_score)
    infra_score.set(report.infra_score)
    security_score.set(report.security_score)
    queue_pressure_score.set(report.runtime.queue_pressure_score)
    operational_status_gauge.set(_STATUS_ENCODING.get(report.operational_status, 0))
    safe_mode_active.set(1 if report.safe_mode else 0)
    degradation_detected.set(1 if report.degradation_detected else 0)
    invalid_decision_ratio.set(report.quant.invalid_decision_ratio)

    if report.runtime.scheduler_heartbeat_age_seconds is not None:
        scheduler_heartbeat_age_seconds_gauge.set(report.runtime.scheduler_heartbeat_age_seconds)

    if report.datasets.crypto_raw_age_seconds is not None:
        dataset_latest_age_seconds.labels(module="crypto").set(report.datasets.crypto_raw_age_seconds)

    if report.replayability.replay_age_seconds is not None:
        replayability_age_seconds.set(report.replayability.replay_age_seconds)
