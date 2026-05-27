"""Tests for OperationalConfidenceEngine — score computation and classification."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.operational_truth.dto import (
    DatasetTruth,
    InfraTruth,
    QuantTruth,
    ReplayabilityTruth,
    RuntimeTruth,
    SecurityTruth,
    classify_score,
)
from app.operational_truth.engine import compute_confidence


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _runtime(score: int = 90, **kwargs) -> RuntimeTruth:
    defaults = dict(
        score=score,
        status=classify_score(score),
        scheduler_alive=True,
        scheduler_heartbeat_age_seconds=30.0,
        scheduler_consecutive_failures=0,
        scheduler_stale=False,
        worker_alive=True,
        worker_heartbeat_age_seconds=60.0,
        queue_backlog=0,
        queue_pressure_score=0,
        restart_loop_detected=False,
        fail_open_risk=False,
        findings=[],
        evaluated_at=_now(),
    )
    defaults.update(kwargs)
    return RuntimeTruth(**defaults)


def _dataset(score: int = 90, **kwargs) -> DatasetTruth:
    defaults = dict(
        score=score,
        status=classify_score(score),
        crypto_raw_age_seconds=600,
        crypto_normalization_lag_seconds=300,
        crypto_analytics_lag_seconds=600,
        raw_pending=0,
        raw_failed=0,
        schema_drift_detected=False,
        append_only_violations=0,
        ingestion_lag_critical=False,
        findings=[],
        evaluated_at=_now(),
    )
    defaults.update(kwargs)
    return DatasetTruth(**defaults)


def _replay(score: int = 90, **kwargs) -> ReplayabilityTruth:
    defaults = dict(
        score=score,
        determinism_score=90,
        reconstruction_confidence=90,
        status=classify_score(score),
        sequence_gaps_detected=False,
        missing_events_estimated=0,
        snapshot_consistency=True,
        replay_files_found=6,
        replay_age_seconds=120.0,
        findings=[],
        evaluated_at=_now(),
    )
    defaults.update(kwargs)
    return ReplayabilityTruth(**defaults)


def _quant(score: int = 85, **kwargs) -> QuantTruth:
    defaults = dict(
        score=score,
        status=classify_score(score),
        source="live",
        confidence_drift_detected=False,
        entropy_spike_detected=False,
        invalid_decision_ratio=0.1,
        hold_effectiveness=None,
        calibration_ok=True,
        strategy_stable=True,
        findings=[],
        evaluated_at=_now(),
    )
    defaults.update(kwargs)
    return QuantTruth(**defaults)


def _infra(score: int = 100, **kwargs) -> InfraTruth:
    defaults = dict(
        score=score,
        status=classify_score(score),
        postgres_ok=True,
        redis_ok=True,
        redis_required=False,
        findings=[],
        evaluated_at=_now(),
    )
    defaults.update(kwargs)
    return InfraTruth(**defaults)


def _security(score: int = 80, **kwargs) -> SecurityTruth:
    defaults = dict(
        score=score,
        status=classify_score(score),
        auth_enabled=True,
        dry_run_active=False,
        api_key_protected=True,
        hardcoded_secrets_risk=False,
        findings=[],
        evaluated_at=_now(),
    )
    defaults.update(kwargs)
    return SecurityTruth(**defaults)


class TestClassifyScore:
    def test_healthy(self):
        assert classify_score(100) == "HEALTHY"
        assert classify_score(80) == "HEALTHY"

    def test_degraded(self):
        assert classify_score(79) == "DEGRADED"
        assert classify_score(60) == "DEGRADED"

    def test_partially_unsafe(self):
        assert classify_score(59) == "PARTIALLY_UNSAFE"
        assert classify_score(40) == "PARTIALLY_UNSAFE"

    def test_unsafe(self):
        assert classify_score(39) == "UNSAFE"
        assert classify_score(20) == "UNSAFE"

    def test_critical(self):
        assert classify_score(19) == "CRITICAL"
        assert classify_score(0) == "CRITICAL"


class TestComputeConfidence:
    def test_all_healthy(self):
        conf = compute_confidence(
            _runtime(90), _dataset(90), _replay(90), _quant(85), _infra(100), _security(80)
        )
        assert conf.operational_confidence_score >= 80
        assert conf.status == "HEALTHY"
        assert not conf.safe_mode
        assert not conf.degradation_detected

    def test_postgres_down_is_critical(self):
        conf = compute_confidence(
            _runtime(90), _dataset(90), _replay(90), _quant(85),
            _infra(0, postgres_ok=False, redis_ok=False),
            _security(80),
        )
        assert conf.status == "CRITICAL"
        assert conf.operational_confidence_score <= 15

    def test_safe_mode_below_40(self):
        conf = compute_confidence(
            _runtime(10), _dataset(10), _replay(10), _quant(10), _infra(30), _security(40)
        )
        assert conf.safe_mode is True

    def test_degradation_detected_when_not_healthy(self):
        conf = compute_confidence(
            _runtime(50), _dataset(50), _replay(50), _quant(50), _infra(70), _security(70)
        )
        assert conf.degradation_detected is True

    def test_critical_findings_collected(self):
        runtime = _runtime(30, findings=["scheduler_dead: 1800s old"])
        infra = _infra(0, postgres_ok=False, findings=["postgres_unavailable: timeout"])
        conf = compute_confidence(runtime, _dataset(), _replay(), _quant(), infra, _security())
        assert any("dead" in f or "unavailable" in f for f in conf.critical_findings)

    def test_recommendations_generated_on_issues(self):
        runtime = _runtime(30, scheduler_alive=False, worker_alive=False, queue_backlog=300)
        conf = compute_confidence(runtime, _dataset(), _replay(), _quant(), _infra(), _security())
        assert len(conf.recommendations) > 0

    def test_score_bounded_0_100(self):
        conf = compute_confidence(
            _runtime(0), _dataset(0), _replay(0), _quant(0), _infra(0), _security(0)
        )
        assert 0 <= conf.operational_confidence_score <= 100


class TestDegradationScenarios:
    def test_scheduler_restart_loop(self):
        runtime = _runtime(
            score=40,
            scheduler_alive=True,
            restart_loop_detected=True,
            scheduler_consecutive_failures=5,
            findings=["scheduler_restart_loop: 5 consecutive failures"],
        )
        conf = compute_confidence(runtime, _dataset(), _replay(), _quant(), _infra(), _security())
        assert conf.degradation_detected

    def test_queue_explosion(self):
        runtime = _runtime(score=30, queue_backlog=600, queue_pressure_score=100)
        conf = compute_confidence(runtime, _dataset(), _replay(), _quant(), _infra(), _security())
        assert conf.degradation_detected

    def test_stale_dataset(self):
        datasets = _dataset(
            score=20,
            crypto_raw_age_seconds=90000,
            ingestion_lag_critical=True,
            findings=["crypto_raw_stale: 90000s old (>24h)"],
        )
        conf = compute_confidence(_runtime(), datasets, _replay(), _quant(), _infra(), _security())
        assert conf.status in ("DEGRADED", "PARTIALLY_UNSAFE", "UNSAFE", "CRITICAL")

    def test_entropy_spike(self):
        quant = _quant(score=30, entropy_spike_detected=True, invalid_decision_ratio=0.8)
        conf = compute_confidence(_runtime(), _dataset(), _replay(), quant, _infra(), _security())
        # quant score is reflected in the weighted score and recommendations
        assert conf.quant_reliability_score == 30
        assert any("entropy" in r.lower() or "invalid" in r.lower() for r in conf.recommendations)

    def test_replay_gaps(self):
        replay = _replay(score=30, sequence_gaps_detected=True, missing_events_estimated=5)
        conf = compute_confidence(_runtime(), _dataset(), replay, _quant(), _infra(), _security())
        assert conf.degradation_detected
