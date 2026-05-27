"""Integration-style tests for individual analyzers using mocked dependencies."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.operational_truth.analyzers.replayability import analyze_replayability
from app.operational_truth.analyzers.security import analyze_security
from app.operational_truth.analyzers.runtime import _queue_pressure
from app.operational_truth.safety import evaluate_safety, SafetyDecision
from app.operational_truth.dto import OperationalConfidence, classify_score


# ── Queue pressure ────────────────────────────────────────────────────────────

class TestQueuePressure:
    def test_empty_queue(self):
        assert _queue_pressure(0) == 0

    def test_small_backlog(self):
        assert _queue_pressure(25) == 20

    def test_medium_backlog(self):
        assert _queue_pressure(150) == 50

    def test_large_backlog(self):
        assert _queue_pressure(400) == 75

    def test_explosion(self):
        assert _queue_pressure(1000) == 100


# ── Replayability ─────────────────────────────────────────────────────────────

class TestReplayabilityAnalyzer:
    def test_no_runtime_data_dir(self, tmp_path):
        with patch("app.operational_truth.analyzers.replayability.RUNTIME_DATA_DIR", tmp_path / "nonexistent"):
            result = analyze_replayability()
        assert result.replay_files_found == 0
        assert result.score < 80

    def test_with_all_files(self, tmp_path):
        for name in [
            "scheduler_heartbeat.json",
            "worker_heartbeat.json",
            "scheduler_watchdog_snapshot.json",
            "scheduler_execution_drift.jsonl",
            "scheduler_lifecycle.jsonl",
            "stability_log.jsonl",
            "governance_history.jsonl",
        ]:
            (tmp_path / name).write_text("{}", encoding="utf-8")
        with patch("app.operational_truth.analyzers.replayability.RUNTIME_DATA_DIR", tmp_path):
            result = analyze_replayability()
        assert result.replay_files_found > 0
        assert result.snapshot_consistency is True
        assert result.score >= 60

    def test_corrupt_heartbeat(self, tmp_path):
        (tmp_path / "scheduler_heartbeat.json").write_text("{invalid json", encoding="utf-8")
        with patch("app.operational_truth.analyzers.replayability.RUNTIME_DATA_DIR", tmp_path):
            result = analyze_replayability()
        assert result.snapshot_consistency is False

    def test_sequence_gap_detection(self, tmp_path):
        records = [
            json.dumps({"timestamp": "2026-01-01T00:00:00+00:00"}),
            json.dumps({"timestamp": "2026-01-01T05:00:00+00:00"}),  # 5h gap
        ]
        (tmp_path / "scheduler_backlog_history.jsonl").write_text(
            "\n".join(records), encoding="utf-8"
        )
        with patch("app.operational_truth.analyzers.replayability.RUNTIME_DATA_DIR", tmp_path):
            result = analyze_replayability()
        assert result.sequence_gaps_detected is True


# ── Security ──────────────────────────────────────────────────────────────────

class TestSecurityAnalyzer:
    def test_auth_disabled_dev(self):
        with patch("app.operational_truth.analyzers.security.settings") as mock_settings:
            mock_settings.api_key_enabled = False
            mock_settings.api_key = ""
            mock_settings.app_env = "development"
            mock_settings.database_url = "postgresql+psycopg://appuser:strongpass123@localhost/db"
            result = analyze_security()
        assert not result.auth_enabled
        # In development, auth disabled is advisory only (small penalty)
        assert result.score >= 90

    def test_auth_disabled_production(self):
        with patch("app.operational_truth.analyzers.security.settings") as mock_settings:
            mock_settings.api_key_enabled = False
            mock_settings.api_key = ""
            mock_settings.app_env = "production"
            mock_settings.database_url = "postgresql+psycopg://app:strongpass@host/db"
            result = analyze_security()
        assert any("production" in f for f in result.findings)
        assert result.score < 80

    def test_hardcoded_default_password(self):
        with patch("app.operational_truth.analyzers.security.settings") as mock_settings:
            mock_settings.api_key_enabled = True
            mock_settings.api_key = "mykey"
            mock_settings.app_env = "development"
            mock_settings.database_url = "postgresql+psycopg://data_core:data_core@localhost/data_core"
            result = analyze_security()
        assert result.hardcoded_secrets_risk is True
        assert result.score < 100


# ── Safety engine ─────────────────────────────────────────────────────────────

class TestSafetyEngine:
    def _confidence(self, score: int, safe_mode: bool = None, infra_score: int = 100):
        if safe_mode is None:
            safe_mode = score < 40
        return type("C", (), {
            "operational_confidence_score": score,
            "safe_mode": safe_mode,
            "infra_score": infra_score,
        })()

    def test_nominal(self):
        decision = evaluate_safety(self._confidence(85))
        assert decision.severity == "none"
        assert not decision.kill_switch
        assert not decision.fail_closed

    def test_pressure_protection(self):
        decision = evaluate_safety(self._confidence(45))
        assert decision.pressure_protection is True
        assert decision.severity == "warning"

    def test_safe_mode(self):
        decision = evaluate_safety(self._confidence(35))
        assert decision.safe_mode is True
        assert decision.severity == "critical"

    def test_fail_closed(self):
        decision = evaluate_safety(self._confidence(25))
        assert decision.fail_closed is True
        assert decision.severity == "critical"

    def test_kill_switch_emergency(self):
        decision = evaluate_safety(self._confidence(10))
        assert decision.kill_switch is True
        assert decision.severity == "emergency"

    def test_infra_failure_triggers_fail_closed(self):
        decision = evaluate_safety(self._confidence(70, infra_score=30))
        assert decision.fail_closed is True
