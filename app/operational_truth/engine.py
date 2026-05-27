"""OperationalConfidenceEngine — weighted score aggregation and classification."""

from __future__ import annotations

from datetime import datetime, timezone

from app.operational_truth.dto import (
    DatasetTruth,
    InfraTruth,
    OperationalConfidence,
    OperationalStatus,
    QuantTruth,
    ReplayabilityTruth,
    RuntimeTruth,
    SecurityTruth,
    classify_score,
)

# Weights must sum to 1.0
_WEIGHTS = {
    "runtime": 0.25,
    "dataset": 0.22,
    "replayability": 0.18,
    "quant": 0.15,
    "infra": 0.12,
    "security": 0.05,
    "observability": 0.03,  # bonus: presence of all analyzers = observability
}

# Safe mode threshold
_SAFE_MODE_THRESHOLD = 40

# Observability score: a fixed bonus when all subsystems are reachable
_OBSERVABILITY_SCORE = 80


def _build_recommendations(
    runtime: RuntimeTruth,
    datasets: DatasetTruth,
    replayability: ReplayabilityTruth,
    quant: QuantTruth,
    infra: InfraTruth,
    security: SecurityTruth,
) -> list[str]:
    recs: list[str] = []

    if not runtime.scheduler_alive:
        recs.append("Restart the scheduler container — heartbeat is dead or stale.")
    if runtime.restart_loop_detected:
        recs.append("Investigate scheduler consecutive failures — potential restart loop.")
    if runtime.queue_backlog > 200:
        recs.append(f"Drain normalization queue ({runtime.queue_backlog} pending) before further collection.")
    if not runtime.worker_alive:
        recs.append("Worker process appears dead — check container logs and restart.")

    if datasets.ingestion_lag_critical:
        recs.append("Crypto ingestion lag is critical — verify collector job and data source connectivity.")
    if datasets.raw_failed > 0:
        recs.append(f"Clear {datasets.raw_failed} failed raw records or investigate failure root cause.")

    if not replayability.snapshot_consistency:
        recs.append("Heartbeat files are corrupted — investigate and repair runtime-data volume.")
    if replayability.sequence_gaps_detected:
        recs.append("Sequence gaps detected in replay history — audit scheduler_backlog_history.jsonl.")

    if quant.entropy_spike_detected:
        recs.append("Signal entropy spike detected — review signal generator calibration.")
    if quant.invalid_decision_ratio > 0.5:
        recs.append("High invalid decision ratio — review rejection filters and signal thresholds.")

    if not infra.postgres_ok:
        recs.append("PostgreSQL is unreachable — immediate attention required.")
    if not infra.redis_ok and infra.redis_required:
        recs.append("Redis is unreachable but required — check Redis container and connection string.")

    if security.hardcoded_secrets_risk:
        recs.append("Replace default credentials in DATABASE_URL with strong unique passwords.")
    if not security.auth_enabled:
        recs.append("Enable API key authentication before deploying to production.")

    return recs


def compute_confidence(
    runtime: RuntimeTruth,
    datasets: DatasetTruth,
    replayability: ReplayabilityTruth,
    quant: QuantTruth,
    infra: InfraTruth,
    security: SecurityTruth,
) -> OperationalConfidence:
    now = datetime.now(timezone.utc)

    weighted = (
        runtime.score * _WEIGHTS["runtime"]
        + datasets.score * _WEIGHTS["dataset"]
        + replayability.score * _WEIGHTS["replayability"]
        + quant.score * _WEIGHTS["quant"]
        + infra.score * _WEIGHTS["infra"]
        + security.score * _WEIGHTS["security"]
        + _OBSERVABILITY_SCORE * _WEIGHTS["observability"]
    )
    overall_score = max(0, min(100, int(weighted)))

    status: OperationalStatus = classify_score(overall_score)

    # Infra degradation overrides score classification upward (can never be healthy when infra fails)
    if not infra.postgres_ok:
        status = "CRITICAL"
        overall_score = min(overall_score, 15)

    safe_mode = overall_score < _SAFE_MODE_THRESHOLD
    degradation_detected = status not in ("HEALTHY",)

    critical_findings: list[str] = []
    warnings: list[str] = []
    for finding in runtime.findings + datasets.findings + infra.findings + security.findings:
        if any(kw in finding for kw in ("dead", "missing", "critical", "explosion", "unavailable", "corrupt")):
            critical_findings.append(finding)
        else:
            warnings.append(finding)
    for finding in replayability.findings + quant.findings:
        warnings.append(finding)

    recommendations = _build_recommendations(runtime, datasets, replayability, quant, infra, security)

    return OperationalConfidence(
        operational_confidence_score=overall_score,
        status=status,
        runtime_score=runtime.score,
        dataset_score=datasets.score,
        replayability_score=replayability.score,
        quant_reliability_score=quant.score,
        infra_score=infra.score,
        security_score=security.score,
        degradation_detected=degradation_detected,
        safe_mode=safe_mode,
        critical_findings=critical_findings,
        warnings=warnings,
        recommendations=recommendations,
        evaluated_at=now,
    )
