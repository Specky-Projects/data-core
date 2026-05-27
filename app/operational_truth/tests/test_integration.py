"""Integration tests for ProductionReadinessService and full evaluation pipeline.

These tests use a real in-memory SQLite DB (via SQLAlchemy) to avoid needing
a running Postgres instance. They mock external calls (heartbeat files, Redis,
poupi-crypto HTTP).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from database.models import Base

    _HAS_DB = True
except Exception:
    _HAS_DB = False


@pytest.fixture()
def in_memory_db():
    if not _HAS_DB:
        pytest.skip("SQLAlchemy models not importable in this test context")
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


class TestProductionReadinessFull:
    def test_evaluate_returns_report(self, in_memory_db, tmp_path):
        from app.operational_truth.production_readiness import ProductionReadinessService

        with (
            patch("app.operational_truth.analyzers.replayability.RUNTIME_DATA_DIR", tmp_path),
            patch("app.operational_truth.analyzers.quant._fetch_crypto_status", return_value=None),
            patch("app.operational_truth.analyzers.quant._fetch_crypto_metrics_text", return_value=None),
            patch("app.operational_truth.analyzers.infra.settings") as mock_settings,
            patch("app.operational_truth.analyzers.security.settings") as mock_sec,
            patch("app.operational_truth.analyzers.runtime.settings") as mock_rt,
            patch("app.operational_truth.production_readiness.settings") as mock_main,
        ):
            for m in [mock_settings, mock_sec, mock_rt, mock_main]:
                m.cache_enabled = False
                m.redis_url = "redis://localhost:6379/0"
                m.api_key_enabled = False
                m.api_key = ""
                m.app_env = "development"
                m.database_url = "sqlite:///:memory:"
                m.scheduler_enabled = False
                m.worker_pipeline_interval_seconds = 300

            svc = ProductionReadinessService(in_memory_db)
            report = svc.evaluate()

        assert report.operational_confidence_score >= 0
        assert report.operational_confidence_score <= 100
        assert report.status in ("OK", "WARNING", "CRITICAL")
        assert report.operational_status in ("HEALTHY", "DEGRADED", "PARTIALLY_UNSAFE", "UNSAFE", "CRITICAL")
        assert isinstance(report.critical_findings, list)
        assert isinstance(report.recommendations, list)
        assert isinstance(report.generated_at, datetime)

    def test_stale_scheduler_degrades_runtime_score(self, tmp_path):
        from app.operational_truth.analyzers import runtime as rt_mod
        from app.operational_truth.analyzers.runtime import analyze_runtime

        stale_hb = {
            "last_job": "normalize_job",
            "last_job_at": "2020-01-01T00:00:00+00:00",
            "consecutive_failures": 0,
            "written_at": "2020-01-01T00:00:00+00:00",
            "pid": 1,
        }

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        with (
            patch.object(rt_mod, "read_scheduler_heartbeat", return_value=stale_hb),
            patch.object(rt_mod, "heartbeat_age_seconds", return_value=4000.0),
            patch.object(rt_mod, "_worker_heartbeat_age", return_value=(False, None)),
            patch("app.operational_truth.analyzers.runtime.settings") as mock_settings,
        ):
            mock_settings.scheduler_enabled = True
            mock_settings.worker_pipeline_interval_seconds = 300
            result = analyze_runtime(mock_db)

        assert result.scheduler_stale or not result.scheduler_alive
        assert result.score < 80

    def test_queue_explosion_detected(self, tmp_path):
        from app.operational_truth.analyzers.runtime import analyze_runtime

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.count.return_value = 600

        with (
            patch("app.operational_truth.analyzers.runtime.read_scheduler_heartbeat", return_value=None),
            patch("app.operational_truth.analyzers.runtime.heartbeat_age_seconds", return_value=None),
            patch("app.operational_truth.analyzers.runtime._worker_heartbeat_age", return_value=(True, 30.0)),
            patch("app.operational_truth.analyzers.runtime.settings") as mock_settings,
        ):
            mock_settings.scheduler_enabled = False
            mock_settings.worker_pipeline_interval_seconds = 300
            result = analyze_runtime(mock_db)

        assert result.queue_backlog == 600
        assert result.queue_pressure_score == 100
        assert any("explosion" in f for f in result.findings)

    def test_fail_open_detected(self):
        from app.operational_truth.analyzers.runtime import analyze_runtime

        alive_hb = {
            "last_job": "normalize_job",
            "last_job_at": datetime.now(timezone.utc).isoformat(),
            "consecutive_failures": 3,
            "written_at": datetime.now(timezone.utc).isoformat(),
            "pid": 1,
        }

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.count.return_value = 150

        with (
            patch("app.operational_truth.analyzers.runtime.read_scheduler_heartbeat", return_value=alive_hb),
            patch("app.operational_truth.analyzers.runtime.heartbeat_age_seconds", return_value=60.0),
            patch("app.operational_truth.analyzers.runtime._worker_heartbeat_age", return_value=(True, 30.0)),
            patch("app.operational_truth.analyzers.runtime.settings") as mock_settings,
        ):
            mock_settings.scheduler_enabled = True
            mock_settings.worker_pipeline_interval_seconds = 300
            result = analyze_runtime(mock_db)

        assert result.fail_open_risk is True
        assert any("fail_open" in f for f in result.findings)

    def test_operational_confidence_calculation_end_to_end(self):
        from app.operational_truth.dto import (
            RuntimeTruth, DatasetTruth, ReplayabilityTruth,
            QuantTruth, InfraTruth, SecurityTruth, classify_score,
        )
        from app.operational_truth.engine import compute_confidence
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)

        # Simulate a healthy-but-degraded system
        runtime = RuntimeTruth(
            score=70, status="DEGRADED",
            scheduler_alive=True, scheduler_heartbeat_age_seconds=200.0,
            scheduler_consecutive_failures=1, scheduler_stale=False,
            worker_alive=True, worker_heartbeat_age_seconds=120.0,
            queue_backlog=80, queue_pressure_score=50,
            restart_loop_detected=False, fail_open_risk=False,
            findings=["queue_pressure_moderate: 80 pending items"],
            evaluated_at=now,
        )
        datasets = DatasetTruth(
            score=65, status="DEGRADED",
            crypto_raw_age_seconds=4000, crypto_normalization_lag_seconds=2000,
            crypto_analytics_lag_seconds=3000, raw_pending=80, raw_failed=0,
            schema_drift_detected=False, append_only_violations=0,
            ingestion_lag_critical=False, findings=[], evaluated_at=now,
        )
        replay = ReplayabilityTruth(
            score=80, determinism_score=85, reconstruction_confidence=80,
            status="HEALTHY", sequence_gaps_detected=False,
            missing_events_estimated=0, snapshot_consistency=True,
            replay_files_found=5, replay_age_seconds=300.0,
            findings=[], evaluated_at=now,
        )
        quant = QuantTruth(
            score=75, status="DEGRADED", source="live",
            confidence_drift_detected=False, entropy_spike_detected=False,
            invalid_decision_ratio=0.2, hold_effectiveness=None,
            calibration_ok=True, strategy_stable=True,
            findings=[], evaluated_at=now,
        )
        infra = InfraTruth(
            score=100, status="HEALTHY",
            postgres_ok=True, redis_ok=True, redis_required=False,
            findings=[], evaluated_at=now,
        )
        security = SecurityTruth(
            score=85, status="HEALTHY",
            auth_enabled=True, dry_run_active=False, api_key_protected=True,
            hardcoded_secrets_risk=False, findings=[], evaluated_at=now,
        )

        conf = compute_confidence(runtime, datasets, replay, quant, infra, security)

        # With all scores in the 65-100 range, overall should be DEGRADED or HEALTHY
        assert conf.status in ("HEALTHY", "DEGRADED")
        assert conf.operational_confidence_score >= 60
        assert not conf.safe_mode
        assert conf.degradation_detected  # at least one sub-system is DEGRADED
