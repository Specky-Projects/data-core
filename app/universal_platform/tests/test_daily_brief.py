"""Tests for the Unified Daily Brief (WS6)."""
from __future__ import annotations

from app.universal_platform.adapters import (
    AffiliateAdapter,
    InfrastructureAdapter,
    PoupiBabyAdapter,
)
from app.universal_platform.alert_engine import UnifiedAlertEngine
from app.universal_platform.daily_brief import SECTION_ORDER, DailyBriefBuilder


def _sample_records():
    return [
        PoupiBabyAdapter().observe({"event_type": "opportunity.discovered", "product": "Fralda X",
                                    "occurred_at": "2026-06-30T09:00:00Z", "confidence": 0.9}),
        AffiliateAdapter().observe({"event_type": "conversion", "product_id": "p1", "revenue": 42.0,
                                    "occurred_at": "2026-06-30T09:30:00Z", "confidence": 0.8}),
        InfrastructureAdapter().observe({"component": "postgres", "event_type": "postgres.down",
                                         "service": "pg1", "occurred_at": "2026-06-30T10:00:00Z"}),
    ]


def test_brief_has_all_canonical_sections() -> None:
    records = _sample_records()
    alerts = UnifiedAlertEngine().evaluate(records)
    brief = DailyBriefBuilder().build(records, alerts=alerts, generated_at="2026-06-30")
    titles = [s.title for s in brief.sections]
    assert titles == list(SECTION_ORDER)


def test_brief_is_single_consolidated_report() -> None:
    brief = DailyBriefBuilder().build(_sample_records(), generated_at="2026-06-30")
    # one brief object, not many
    assert brief.brief_id
    assert brief.advisory_only is True


def test_open_alerts_section_reflects_alerts() -> None:
    records = _sample_records()
    alerts = UnifiedAlertEngine().evaluate(records)
    brief = DailyBriefBuilder().build(records, alerts=alerts, generated_at="2026-06-30")
    section = next(s for s in brief.sections if s.title == "Open Alerts")
    assert section.metrics.get("count") == len(alerts)
    assert len(alerts) >= 1  # postgres.down is CRITICAL


def test_top_opportunities_sorted_by_confidence() -> None:
    brief = DailyBriefBuilder().build(_sample_records(), generated_at="2026-06-30")
    section = next(s for s in brief.sections if s.title == "Top Opportunities")
    # poupi-baby (0.9) should appear before affiliate (0.8)
    joined = "\n".join(section.lines)
    assert joined.index("Fralda X") < joined.index("p1")


def test_scientific_health_is_ratio() -> None:
    brief = DailyBriefBuilder().build(_sample_records(), generated_at="2026-06-30")
    assert 0.0 <= brief.scientific_health <= 1.0


def test_render_markdown_deterministic() -> None:
    records = _sample_records()
    builder = DailyBriefBuilder()
    md1 = builder.build(records, generated_at="2026-06-30").render_markdown()
    md2 = builder.build(records, generated_at="2026-06-30").render_markdown()
    assert md1 == md2
    assert md1.startswith("# Business OS Daily — 2026-06-30")
    assert "## Executive Summary" in md1


def test_empty_brief_still_renders() -> None:
    brief = DailyBriefBuilder().build([], generated_at="2026-06-30")
    assert brief.scientific_health == 1.0
    md = brief.render_markdown()
    assert "No activity observed." in md
