"""Tests for PolicyContract generation and the /policy/operational endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.operational_truth.dto import classify_score, ProductionReadinessReport
from app.operational_truth.policy.contract import (
    OperationalPolicyContract,
    blocked_actions_for,
    allowed_actions_for,
    default_enforcement_mode,
    CONTRACT_TTL_SECONDS,
    ALL_ACTIONS,
)
from app.operational_truth.policy.generator import generate_policy


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_report(
    confidence: int = 85,
    operational_status: str = "HEALTHY",
    safe_mode: bool = False,
    infra_score: int = 100,
    critical_findings: list[str] | None = None,
    warnings: list[str] | None = None,
) -> "ProductionReadinessReport":
    from app.operational_truth.dto import (
        RuntimeTruth, DatasetTruth, ReplayabilityTruth,
        QuantTruth, InfraTruth, SecurityTruth,
    )
    now = datetime.now(timezone.utc)
    status = classify_score(confidence)

    def _t(score, **kw):
        return {
            "score": score, "status": classify_score(score),
            "findings": [], "evaluated_at": now, **kw,
        }

    runtime = RuntimeTruth(
        **_t(confidence),
        scheduler_alive=True, scheduler_heartbeat_age_seconds=30.0,
        scheduler_consecutive_failures=0, scheduler_stale=False,
        worker_alive=True, worker_heartbeat_age_seconds=60.0,
        queue_backlog=0, queue_pressure_score=0,
        restart_loop_detected=False, fail_open_risk=False,
    )
    datasets = DatasetTruth(
        **_t(confidence),
        crypto_raw_age_seconds=600, crypto_normalization_lag_seconds=300,
        crypto_analytics_lag_seconds=600, raw_pending=0, raw_failed=0,
        schema_drift_detected=False, append_only_violations=0,
        ingestion_lag_critical=False,
    )
    replay = ReplayabilityTruth(
        **_t(confidence),
        determinism_score=confidence, reconstruction_confidence=confidence,
        sequence_gaps_detected=False, missing_events_estimated=0,
        snapshot_consistency=True, replay_files_found=5, replay_age_seconds=120.0,
    )
    quant = QuantTruth(
        **_t(confidence),
        source="live", confidence_drift_detected=False,
        entropy_spike_detected=False, invalid_decision_ratio=0.1,
        hold_effectiveness=None, calibration_ok=True, strategy_stable=True,
    )
    infra = InfraTruth(
        **_t(infra_score),
        postgres_ok=True, redis_ok=True, redis_required=False,
    )
    security = SecurityTruth(
        **_t(85),
        auth_enabled=True, dry_run_active=False,
        api_key_protected=True, hardcoded_secrets_risk=False,
    )

    from app.operational_truth.dto import readiness_from_status
    return ProductionReadinessReport(
        status=readiness_from_status(operational_status),
        operational_confidence_score=confidence,
        operational_status=operational_status,
        runtime_score=confidence,
        dataset_score=confidence,
        replayability_score=confidence,
        quant_reliability_score=confidence,
        infra_score=infra_score,
        security_score=85,
        degradation_detected=operational_status != "HEALTHY",
        safe_mode=safe_mode,
        critical_findings=critical_findings or [],
        warnings=warnings or [],
        recommendations=[],
        runtime=runtime,
        datasets=datasets,
        replayability=replay,
        quant=quant,
        infra=infra,
        security=security,
        generated_at=now,
        environment="test",
    )


class TestDefaultEnforcementMode:
    def test_healthy_maps_to_observe_only(self):
        assert default_enforcement_mode("HEALTHY") == "observe_only"

    def test_degraded_maps_to_warn_only(self):
        assert default_enforcement_mode("DEGRADED") == "warn_only"

    def test_partially_unsafe_maps_to_safe_mode(self):
        assert default_enforcement_mode("PARTIALLY_UNSAFE") == "safe_mode"

    def test_unsafe_maps_to_fail_closed(self):
        assert default_enforcement_mode("UNSAFE") == "fail_closed"

    def test_critical_maps_to_kill_switch(self):
        assert default_enforcement_mode("CRITICAL") == "emergency_kill_switch"

    def test_unknown_maps_to_safe_mode(self):
        assert default_enforcement_mode("UNKNOWN_STATUS") == "safe_mode"


class TestBlockedActionsForMode:
    def test_observe_only_blocks_nothing(self):
        assert blocked_actions_for("observe_only") == []

    def test_warn_only_blocks_nothing(self):
        assert blocked_actions_for("warn_only") == []

    def test_safe_mode_blocks_nothing(self):
        assert blocked_actions_for("safe_mode") == []

    def test_fail_closed_blocks_position_open(self):
        assert "position_open" in blocked_actions_for("fail_closed")

    def test_kill_switch_blocks_position_and_signal(self):
        blocked = blocked_actions_for("emergency_kill_switch")
        assert "position_open" in blocked
        assert "signal_generate" in blocked

    def test_allowed_is_complement_of_blocked(self):
        for mode in ["observe_only", "warn_only", "safe_mode", "fail_closed", "emergency_kill_switch"]:
            blocked = set(blocked_actions_for(mode))
            allowed = set(allowed_actions_for(mode))
            assert not (blocked & allowed), f"mode {mode}: actions in both allowed and blocked"


class TestGeneratePolicy:
    def test_healthy_report_generates_observe_only(self):
        report = _make_report(confidence=90, operational_status="HEALTHY")
        contract = generate_policy(report)
        assert contract.enforcement_mode == "observe_only"
        assert not contract.safe_mode
        assert not contract.fail_closed
        assert not contract.kill_switch
        assert contract.position_size_multiplier == 1.0

    def test_unsafe_report_generates_fail_closed(self):
        report = _make_report(confidence=30, operational_status="UNSAFE")
        contract = generate_policy(report)
        assert contract.enforcement_mode == "fail_closed"
        assert "position_open" in contract.blocked_actions

    def test_critical_report_generates_kill_switch(self):
        report = _make_report(confidence=10, operational_status="CRITICAL")
        contract = generate_policy(report)
        assert contract.enforcement_mode == "emergency_kill_switch"
        assert contract.kill_switch

    def test_safe_mode_sets_size_multiplier(self):
        report = _make_report(confidence=50, operational_status="PARTIALLY_UNSAFE")
        contract = generate_policy(report)
        assert contract.enforcement_mode == "safe_mode"
        assert contract.position_size_multiplier < 1.0
        assert contract.min_confidence_override is not None

    def test_contract_has_ttl(self):
        from datetime import timedelta
        report = _make_report(confidence=90, operational_status="HEALTHY")
        contract = generate_policy(report)
        delta = contract.expires_at - contract.generated_at
        assert abs(delta.total_seconds() - CONTRACT_TTL_SECONDS) < 5

    def test_contract_not_expired_when_fresh(self):
        report = _make_report(confidence=90, operational_status="HEALTHY")
        contract = generate_policy(report)
        assert not contract.is_expired()

    def test_degradation_reason_set_from_critical_findings(self):
        report = _make_report(
            confidence=20, operational_status="UNSAFE",
            critical_findings=["postgres_unavailable: timeout"],
        )
        contract = generate_policy(report)
        assert contract.degradation_reason == "postgres_unavailable: timeout"

    def test_contract_version_is_current(self):
        from app.operational_truth.policy.contract import CONTRACT_VERSION
        report = _make_report(90, "HEALTHY")
        contract = generate_policy(report)
        assert contract.version == CONTRACT_VERSION

    def test_fail_closed_position_size_zero(self):
        report = _make_report(30, "UNSAFE")
        contract = generate_policy(report)
        assert contract.position_size_multiplier == 0.0

    def test_healthy_allowed_actions_include_all(self):
        report = _make_report(90, "HEALTHY")
        contract = generate_policy(report)
        for action in ALL_ACTIONS:
            assert contract.is_action_allowed(action), f"{action} should be allowed in HEALTHY"

    def test_audit_dict_contains_required_fields(self):
        report = _make_report(85, "HEALTHY")
        contract = generate_policy(report)
        audit = contract.to_audit_dict()
        for key in ["version", "generated_at", "status", "confidence_score", "enforcement_mode",
                    "safe_mode", "fail_closed", "kill_switch", "blocked_actions"]:
            assert key in audit
