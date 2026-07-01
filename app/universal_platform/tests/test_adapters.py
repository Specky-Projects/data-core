"""Tests for the Universal Adapter Layer (WS1–WS4) — all read-only / advisory / shadow."""
from __future__ import annotations

import pytest

from app.universal_platform.adapters import (
    AffiliateAdapter,
    InfrastructureAdapter,
    PoupiBabyAdapter,
    TelegramAdapter,
)
from app.universal_platform.adapters.base import BaseAdapter
from app.universal_platform.events import Severity

ALL_ADAPTERS = [PoupiBabyAdapter, InfrastructureAdapter, TelegramAdapter, AffiliateAdapter]


@pytest.mark.parametrize("cls", ALL_ADAPTERS)
def test_adapter_is_shadow_readonly_advisory(cls) -> None:
    adapter = cls()
    assert adapter.SHADOW_MODE is True
    assert adapter.READ_ONLY is True
    assert adapter.ADVISORY_ONLY is True
    assert isinstance(adapter, BaseAdapter)


@pytest.mark.parametrize("cls", ALL_ADAPTERS)
def test_adapter_records_are_advisory(cls) -> None:
    adapter = cls()
    raw = {"event_type": "click", "component": "redis", "kind": "message",
           "occurred_at": "2026-06-30T10:00:00Z", "entity_id": "x", "product": "x", "product_id": "x"}
    record = adapter.observe(raw)
    assert record.advisory_only is True
    assert record.coverage.is_complete is True


# ── WS1 Poupi Baby ─────────────────────────────────────────────────────────────

def test_poupi_baby_lifecycle_events() -> None:
    adapter = PoupiBabyAdapter()
    for et in ("opportunity.discovered", "plan.created", "article.generated",
               "image.created", "publication.done", "experiment.completed", "result.measured"):
        rec = adapter.observe({"event_type": et, "product": "Fralda X",
                               "occurred_at": "2026-06-30T10:00:00Z", "confidence": 0.7})
        assert rec.event.event_type == et
        assert rec.event.domain == "POUPI_BABY"
        assert rec.coverage.is_complete


def test_poupi_baby_never_executes() -> None:
    rec = PoupiBabyAdapter().observe({"event_type": "opportunity.discovered",
                                      "product": "P", "occurred_at": "2026-06-30T10:00:00Z"})
    facts_raw = rec.scientific.facts
    assert facts_raw.action == "OBSERVE"
    assert facts_raw.simulation_only is True


# ── WS2 Infrastructure ─────────────────────────────────────────────────────────

def test_infra_severity_derivation_from_keyword() -> None:
    rec = InfrastructureAdapter().observe(
        {"component": "redis", "event_type": "redis.crash", "service": "r1",
         "occurred_at": "2026-06-30T10:00:00Z"})
    assert rec.severity is Severity.CRITICAL


def test_infra_severity_component_default() -> None:
    rec = InfrastructureAdapter().observe(
        {"component": "postgres", "event_type": "postgres.slow_query", "service": "pg1",
         "occurred_at": "2026-06-30T10:00:00Z"})
    assert rec.severity is Severity.HIGH


def test_infra_explicit_severity_wins() -> None:
    rec = InfrastructureAdapter().observe(
        {"component": "cpu", "event_type": "cpu.spike", "severity": "CRITICAL",
         "occurred_at": "2026-06-30T10:00:00Z"})
    assert rec.severity is Severity.CRITICAL


def test_infra_metrics_captured() -> None:
    rec = InfrastructureAdapter().observe(
        {"component": "cpu", "event_type": "cpu.high", "cpu": 95, "ram": 80,
         "occurred_at": "2026-06-30T10:00:00Z"})
    assert rec.event.metrics.get("cpu") == 95
    assert rec.event.metrics.get("ram") == 80


# ── WS3 Telegram ───────────────────────────────────────────────────────────────

def test_telegram_command_references_capability_but_does_not_execute() -> None:
    rec = TelegramAdapter().observe(
        {"kind": "command", "command": "daily_brief.generate", "chat_id": "123",
         "occurred_at": "2026-06-30T10:00:00Z"})
    assert rec.event.metadata["capability_ref"] == "daily_brief.generate"
    assert rec.event.event_type == "telegram.command"


def test_telegram_render_outbound_is_shadow() -> None:
    out = TelegramAdapter.render_outbound("alert", "Title", "Body")
    assert out["delivered"] is False
    assert out["advisory_only"] is True


def test_telegram_rejects_unknown_outbound_kind() -> None:
    with pytest.raises(AssertionError):
        TelegramAdapter.render_outbound("execute_trade", "t", "b")


# ── WS4 Affiliate ──────────────────────────────────────────────────────────────

def test_affiliate_revenue_creates_outcome_and_learning() -> None:
    rec = AffiliateAdapter().observe(
        {"event_type": "conversion", "product_id": "p1", "revenue": 42.0,
         "occurred_at": "2026-06-30T10:00:00Z"})
    assert rec.scientific.facts.outcome is not None
    assert rec.scientific.facts.outcome.kind == "SUCCESS"
    # learning stage runs when an outcome exists
    stages = {s.stage.value: s.status.value for s in rec.scientific.pipeline_trace.stages}
    assert stages["LEARNING"] == "PASSED"


def test_affiliate_click_has_no_outcome() -> None:
    rec = AffiliateAdapter().observe(
        {"event_type": "click", "product_id": "p1", "occurred_at": "2026-06-30T10:00:00Z"})
    assert rec.scientific.facts.outcome is None


def test_observe_many() -> None:
    recs = AffiliateAdapter().observe_many([
        {"event_type": "click", "product_id": "p1", "occurred_at": "2026-06-30T10:00:00Z"},
        {"event_type": "conversion", "product_id": "p1", "revenue": 5.0, "occurred_at": "2026-06-30T10:05:00Z"},
    ])
    assert len(recs) == 2
