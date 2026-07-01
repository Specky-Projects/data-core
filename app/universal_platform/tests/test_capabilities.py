"""Tests for Capability Registry Phase 2 wiring — reuse, isolation, advisory enforcement."""
from __future__ import annotations

import pytest

from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.capability_orchestrator.registry import CapabilityRegistry
from app.universal_platform.capabilities import PHASE2_CAPABILITY_IDS, Phase2Platform


def test_all_phase2_capabilities_registered() -> None:
    platform = Phase2Platform()
    registered = set(platform.orchestrator.registered_ids())
    assert set(PHASE2_CAPABILITY_IDS) <= registered


def test_platform_reuses_capability_orchestrator() -> None:
    platform = Phase2Platform()
    assert isinstance(platform.orchestrator, CapabilityOrchestrator)
    assert isinstance(platform.registry, CapabilityRegistry)


def test_adapter_observe_capabilities_route_through_orchestrator() -> None:
    platform = Phase2Platform()
    cases = {
        "poupi.observe": {"event_type": "opportunity.discovered", "product": "P",
                          "occurred_at": "2026-06-30T10:00:00Z"},
        "infra.observe": {"component": "redis", "event_type": "redis.restart", "service": "r1",
                          "occurred_at": "2026-06-30T10:00:00Z"},
        "telegram.observe": {"kind": "message", "chat_id": "1", "occurred_at": "2026-06-30T10:00:00Z"},
        "affiliate.observe": {"event_type": "click", "product_id": "p1",
                              "occurred_at": "2026-06-30T10:00:00Z"},
    }
    for cap_id, event in cases.items():
        resp = platform.execute(cap_id, {"event": event})
        assert resp.advisory_only is True
        assert isinstance(resp.outputs, dict)
        assert resp.outputs["coverage"]["coverage_ratio"] == 1.0


def test_runtime_capabilities() -> None:
    platform = Phase2Platform()
    event = {"project": "infrastructure", "domain": "INFRASTRUCTURE",
             "event_type": "redis.restart", "entity_id": "r1", "occurred_at": "2026-06-30T10:00:00Z"}
    obs = platform.execute("runtime.observe", {"event": event})
    cov = platform.execute("runtime.coverage", {"event": event})
    snap = platform.execute("runtime.snapshot", {"event": event})
    assert obs.outputs["coverage"]["coverage_ratio"] == 1.0
    assert cov.outputs["coverage"]["coverage_ratio"] == 1.0
    assert snap.outputs["audit"]["snapshot_id"]


def test_daily_brief_capability() -> None:
    platform = Phase2Platform()
    events = [
        {"project": "poupi-baby", "event_type": "opportunity.discovered", "product": "P",
         "occurred_at": "2026-06-30T09:00:00Z", "confidence": 0.9},
        {"project": "infrastructure", "component": "postgres", "event_type": "postgres.down",
         "service": "pg1", "occurred_at": "2026-06-30T10:00:00Z"},
    ]
    resp = platform.execute("daily_brief.generate", {"events": events, "generated_at": "2026-06-30"})
    assert len(resp.outputs["sections"]) == 11
    assert resp.advisory_only is True


def test_alert_capabilities() -> None:
    platform = Phase2Platform()
    events = [
        {"project": "infrastructure", "component": "redis", "event_type": "redis.restart",
         "service": "r1", "occurred_at": "2026-06-30T10:00:00Z"},
        {"project": "infrastructure", "component": "scheduler", "event_type": "scheduler.failure",
         "service": "s1", "occurred_at": "2026-06-30T10:01:00Z"},
        {"project": "mirror", "domain": "CRYPTO", "event_type": "mirror.desync", "entity_id": "BTC",
         "occurred_at": "2026-06-30T10:02:00Z", "severity": "HIGH"},
    ]
    ev = platform.execute("alert.evaluate", {"events": events})
    alerts = ev.outputs["alerts"]
    assert any(a["title"] == "Critical Infrastructure Alert" for a in alerts)

    pub = platform.execute("alert.publish", {"alert": alerts[0]})
    assert pub.outputs["published"] is False
    assert pub.outputs["shadow_mode"] is True


def test_unknown_capability_raises() -> None:
    platform = Phase2Platform()
    with pytest.raises(ValueError, match="not registered"):
        platform.execute("does.not.exist", {})


def test_status_reports_shadow_readonly_advisory() -> None:
    status = Phase2Platform().status()
    assert status["advisory_only"] is True
    assert status["shadow_mode"] is True
    assert status["read_only"] is True
    assert len(status["capabilities"]) == len(PHASE2_CAPABILITY_IDS)
