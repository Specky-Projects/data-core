"""DTOs for the Operational Truth Layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Classification ─────────────────────────────────────────────────────────────

OperationalStatus = Literal["HEALTHY", "DEGRADED", "PARTIALLY_UNSAFE", "UNSAFE", "CRITICAL"]
ReadinessStatus = Literal["OK", "WARNING", "CRITICAL"]


def classify_score(score: int) -> OperationalStatus:
    if score >= 80:
        return "HEALTHY"
    if score >= 60:
        return "DEGRADED"
    if score >= 40:
        return "PARTIALLY_UNSAFE"
    if score >= 20:
        return "UNSAFE"
    return "CRITICAL"


def readiness_from_status(status: OperationalStatus) -> ReadinessStatus:
    if status == "HEALTHY":
        return "OK"
    if status in ("DEGRADED", "PARTIALLY_UNSAFE"):
        return "WARNING"
    return "CRITICAL"


# ── Sub-analyzer results ───────────────────────────────────────────────────────

class RuntimeTruth(BaseModel):
    score: int = Field(ge=0, le=100)
    status: OperationalStatus
    scheduler_alive: bool
    scheduler_heartbeat_age_seconds: float | None
    scheduler_consecutive_failures: int
    scheduler_stale: bool
    worker_alive: bool
    worker_heartbeat_age_seconds: float | None
    queue_backlog: int
    queue_pressure_score: int = Field(ge=0, le=100)
    restart_loop_detected: bool
    fail_open_risk: bool
    findings: list[str]
    evaluated_at: datetime


class DatasetTruth(BaseModel):
    score: int = Field(ge=0, le=100)
    status: OperationalStatus
    crypto_raw_age_seconds: int | None
    crypto_normalization_lag_seconds: int | None
    crypto_analytics_lag_seconds: int | None
    raw_pending: int
    raw_failed: int
    schema_drift_detected: bool
    append_only_violations: int
    ingestion_lag_critical: bool
    findings: list[str]
    evaluated_at: datetime


class ReplayabilityTruth(BaseModel):
    score: int = Field(ge=0, le=100)
    determinism_score: int = Field(ge=0, le=100)
    reconstruction_confidence: int = Field(ge=0, le=100)
    status: OperationalStatus
    sequence_gaps_detected: bool
    missing_events_estimated: int
    snapshot_consistency: bool
    replay_files_found: int
    replay_age_seconds: float | None
    findings: list[str]
    evaluated_at: datetime


class QuantTruth(BaseModel):
    score: int = Field(ge=0, le=100)
    status: OperationalStatus
    source: Literal["live", "degraded", "unavailable"]
    confidence_drift_detected: bool
    entropy_spike_detected: bool
    invalid_decision_ratio: float
    hold_effectiveness: float | None
    calibration_ok: bool
    strategy_stable: bool
    findings: list[str]
    evaluated_at: datetime


class InfraTruth(BaseModel):
    score: int = Field(ge=0, le=100)
    status: OperationalStatus
    postgres_ok: bool
    redis_ok: bool
    redis_required: bool
    findings: list[str]
    evaluated_at: datetime


class SecurityTruth(BaseModel):
    score: int = Field(ge=0, le=100)
    status: OperationalStatus
    auth_enabled: bool
    dry_run_active: bool
    api_key_protected: bool
    hardcoded_secrets_risk: bool
    findings: list[str]
    evaluated_at: datetime


# ── Core engine output ─────────────────────────────────────────────────────────

class OperationalConfidence(BaseModel):
    operational_confidence_score: int = Field(ge=0, le=100)
    status: OperationalStatus
    runtime_score: int = Field(ge=0, le=100)
    dataset_score: int = Field(ge=0, le=100)
    replayability_score: int = Field(ge=0, le=100)
    quant_reliability_score: int = Field(ge=0, le=100)
    infra_score: int = Field(ge=0, le=100)
    security_score: int = Field(ge=0, le=100)
    degradation_detected: bool
    safe_mode: bool
    critical_findings: list[str]
    warnings: list[str]
    recommendations: list[str]
    evaluated_at: datetime


# ── Production readiness (top-level) ──────────────────────────────────────────

class ProductionReadinessReport(BaseModel):
    status: ReadinessStatus
    operational_confidence_score: int = Field(ge=0, le=100)
    operational_status: OperationalStatus
    runtime_score: int = Field(ge=0, le=100)
    dataset_score: int = Field(ge=0, le=100)
    replayability_score: int = Field(ge=0, le=100)
    quant_reliability_score: int = Field(ge=0, le=100)
    infra_score: int = Field(ge=0, le=100)
    security_score: int = Field(ge=0, le=100)
    degradation_detected: bool
    safe_mode: bool
    critical_findings: list[str]
    warnings: list[str]
    recommendations: list[str]
    runtime: RuntimeTruth
    datasets: DatasetTruth
    replayability: ReplayabilityTruth
    quant: QuantTruth
    infra: InfraTruth
    security: SecurityTruth
    generated_at: datetime
    environment: str

    def to_health_summary(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "operational_confidence_score": self.operational_confidence_score,
            "operational_status": self.operational_status,
            "degradation_detected": self.degradation_detected,
            "safe_mode": self.safe_mode,
            "critical_findings": self.critical_findings,
            "warnings": self.warnings,
            "generated_at": self.generated_at.isoformat(),
        }
