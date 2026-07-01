"""Tests for the Unified Alert Engine (WS7) — correlation, singletons, evidence, replay."""
from __future__ import annotations

from app.universal_platform.adapters import InfrastructureAdapter, PoupiBabyAdapter
from app.universal_platform.alert_engine import (
    DEFAULT_CORRELATION_RULES,
    UnifiedAlertEngine,
)
from app.universal_platform.events import Severity, UniversalEvent
from app.universal_platform.runtime import UniversalObservationRuntime


def _mirror_record(event_type: str, severity: str = "HIGH"):
    ev = UniversalEvent.create(
        project="mirror", domain="CRYPTO", event_type=event_type, entity_id="BTCUSDT",
        occurred_at="2026-06-30T10:00:00Z", severity=severity)
    return UniversalObservationRuntime().observe(ev)


def _research_record(event_type: str):
    ev = UniversalEvent.create(
        project="research", domain="RESEARCH", event_type=event_type, entity_id="strategy-1",
        occurred_at="2026-06-30T10:00:00Z", severity="HIGH")
    return UniversalObservationRuntime().observe(ev)


def test_critical_infrastructure_correlation() -> None:
    infra = InfrastructureAdapter()
    records = [
        infra.observe({"component": "redis", "event_type": "redis.restart", "service": "r1",
                       "occurred_at": "2026-06-30T10:00:00Z"}),
        infra.observe({"component": "scheduler", "event_type": "scheduler.failure", "service": "s1",
                       "occurred_at": "2026-06-30T10:01:00Z"}),
        _mirror_record("mirror.desync"),
    ]
    alerts = UnifiedAlertEngine().evaluate(records)
    critical = [a for a in alerts if a.title == "Critical Infrastructure Alert"]
    assert len(critical) == 1
    a = critical[0]
    assert a.severity is Severity.CRITICAL
    assert a.root_cause
    assert a.recommended_action
    assert a.replay_ref  # references a pipeline for replay
    assert len(a.evidence) >= 3
    assert a.rule_id == "critical-infrastructure"


def test_scientific_regression_correlation() -> None:
    records = [_research_record("research.regression"), _mirror_record("mirror.degradation")]
    alerts = UnifiedAlertEngine().evaluate(records)
    titles = [a.title for a in alerts]
    assert "Scientific Regression Alert" in titles


def test_correlated_events_not_double_counted_as_singletons() -> None:
    infra = InfrastructureAdapter()
    records = [
        infra.observe({"component": "redis", "event_type": "redis.restart", "service": "r1",
                       "occurred_at": "2026-06-30T10:00:00Z"}),
        infra.observe({"component": "scheduler", "event_type": "scheduler.failure", "service": "s1",
                       "occurred_at": "2026-06-30T10:01:00Z"}),
        _mirror_record("mirror.desync"),
    ]
    alerts = UnifiedAlertEngine().evaluate(records)
    # exactly one alert: the correlated one; the 3 HIGH/CRITICAL records were consumed
    assert len(alerts) == 1


def test_standalone_high_severity_alert() -> None:
    rec = InfrastructureAdapter().observe(
        {"component": "postgres", "event_type": "postgres.down", "service": "pg1",
         "occurred_at": "2026-06-30T10:00:00Z"})
    alerts = UnifiedAlertEngine().evaluate([rec])
    assert len(alerts) == 1
    assert alerts[0].severity is Severity.CRITICAL
    assert alerts[0].rule_id is None


def test_low_severity_produces_no_alert() -> None:
    rec = PoupiBabyAdapter().observe(
        {"event_type": "opportunity.discovered", "product": "P",
         "occurred_at": "2026-06-30T10:00:00Z", "confidence": 0.5})
    assert UnifiedAlertEngine().evaluate([rec]) == []


def test_alerts_sorted_by_severity_desc() -> None:
    infra = InfrastructureAdapter()
    records = [
        infra.observe({"component": "postgres", "event_type": "postgres.down", "service": "pg1",
                       "occurred_at": "2026-06-30T10:00:00Z"}),  # CRITICAL
        infra.observe({"component": "health", "event_type": "health.unhealthy", "service": "api",
                       "occurred_at": "2026-06-30T10:00:00Z"}),  # HIGH
    ]
    alerts = UnifiedAlertEngine().evaluate(records)
    ranks = [a.severity.rank for a in alerts]
    assert ranks == sorted(ranks, reverse=True)


def test_publish_is_shadow_only() -> None:
    rec = InfrastructureAdapter().observe(
        {"component": "postgres", "event_type": "postgres.down", "service": "pg1",
         "occurred_at": "2026-06-30T10:00:00Z"})
    alert = UnifiedAlertEngine().evaluate([rec])[0]
    published = UnifiedAlertEngine().publish(alert)
    assert published["published"] is False
    assert published["shadow_mode"] is True


def test_evaluate_is_deterministic() -> None:
    rec = InfrastructureAdapter().observe(
        {"component": "postgres", "event_type": "postgres.down", "service": "pg1",
         "occurred_at": "2026-06-30T10:00:00Z"})
    a1 = UnifiedAlertEngine().evaluate([rec])[0]
    a2 = UnifiedAlertEngine().evaluate([rec])[0]
    assert a1.alert_id == a2.alert_id


def test_default_rules_present() -> None:
    ids = {r.rule_id for r in DEFAULT_CORRELATION_RULES}
    assert {"critical-infrastructure", "scientific-regression"} <= ids
