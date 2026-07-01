"""Tests for the real (non-synthetic-stub) collectors added in Observer
Framework Phase 1: postgres, redis, scheduler, infra, telegram, mirror
(+ specky/cav generalization).

These adapters query the local dev database via the exact same
SessionLocal() the app itself uses — same as every other data-core test that
touches the DB. Each adapter must degrade gracefully (never raise) when its
data source is unavailable, so failure-path tests monkeypatch SessionLocal to
simulate that.
"""
from __future__ import annotations

from unittest.mock import patch

from app.observation_engine.adapters.infra import InfraAdapter
from app.observation_engine.adapters.mirror import KNOWN_ACCOUNTS, MirrorAdapter
from app.observation_engine.adapters.postgres import PostgresAdapter
from app.observation_engine.adapters.redis_adapter import RedisAdapter
from app.observation_engine.adapters.scheduler import SchedulerAdapter
from app.observation_engine.adapters.telegram import TelegramAdapter
from app.observation_engine.contracts import ObservationHealth, ObservationSeverity
from app.observation_engine.engine import ObservationEngine

REAL_ADAPTER_CLASSES = [PostgresAdapter, RedisAdapter, SchedulerAdapter, InfraAdapter, TelegramAdapter]


# ── Happy path: real data, no fabricated numbers ────────────────────────────

def test_postgres_adapter_reports_real_connection_data() -> None:
    rec = PostgresAdapter().collect()[0]
    assert rec.metrics["reachable"] == 1.0
    assert rec.metrics["active_connections"] >= 0
    assert rec.health is ObservationHealth.HEALTHY


def test_redis_adapter_honest_about_disabled_cache() -> None:
    rec = RedisAdapter().collect()[0]
    # core.config.settings.cache_enabled is False by default in this environment
    from core.config import settings
    if not settings.cache_enabled:
        assert rec.metrics["enabled"] == 0.0
        assert "disabled" in rec.evidence[0].lower()


def test_scheduler_adapter_reports_real_job_count() -> None:
    rec = SchedulerAdapter().collect()[0]
    assert rec.metrics["reachable"] == 1.0
    assert rec.metrics["jobs_registered"] >= 0


def test_infra_adapter_reports_real_disk_and_watchdog() -> None:
    rec = InfraAdapter().collect()[0]
    assert "disk_used_pct" in rec.metrics or "error" in " ".join(rec.evidence)
    assert 0 <= rec.metrics.get("disk_used_pct", 0) <= 100


def test_telegram_adapter_reports_real_delivery_stats() -> None:
    rec = TelegramAdapter().collect()[0]
    assert rec.metrics["reachable"] == 1.0
    assert rec.metrics["total_audited"] >= 0


def test_mirror_adapter_default_account() -> None:
    rec = MirrorAdapter().collect()[0]
    assert rec.source == "mirror-strategy"
    assert rec.project == "poupi-crypto"


def test_mirror_adapter_missing_table_is_info_not_error() -> None:
    """A missing table (schema gap) must never read as a Mirror incident."""
    rec = MirrorAdapter(account="mirror").collect()[0]
    if rec.metrics.get("reachable") == 0.0 and "schema gap" in " ".join(rec.evidence):
        assert rec.severity is ObservationSeverity.INFO
        assert rec.health is ObservationHealth.UNKNOWN


# ── WS2: Specky/CAV generalization ──────────────────────────────────────────

def test_mirror_adapter_accepts_all_known_accounts() -> None:
    for account in KNOWN_ACCOUNTS:
        rec = MirrorAdapter(account=account).collect()[0]
        assert rec.project == "poupi-crypto"


def test_mirror_adapter_rejects_unknown_account() -> None:
    import pytest
    with pytest.raises(ValueError, match="unknown Mirror account"):
        MirrorAdapter(account="nonexistent")


def test_specky_and_cav_produce_independent_snapshots() -> None:
    specky = MirrorAdapter(account="specky").collect()[0]
    cav = MirrorAdapter(account="cav").collect()[0]
    assert specky.source != cav.source
    assert specky.observation_id != cav.observation_id
    assert "specky" in specky.source
    assert "cav" in cav.source


def test_specky_cav_disclose_segmentation_gap_honestly() -> None:
    specky = MirrorAdapter(account="specky").collect()[0]
    assert any("segmentation pending" in e for e in specky.evidence)


# ── Failure path: honest degradation, never a crash ─────────────────────────

@patch("app.observation_engine.adapters.postgres.SessionLocal", side_effect=RuntimeError("db down"))
def test_postgres_adapter_degrades_gracefully_on_db_failure(_mock) -> None:
    rec = PostgresAdapter().collect()[0]
    assert rec.health is ObservationHealth.UNKNOWN
    assert rec.severity is ObservationSeverity.ERROR
    assert rec.metrics["reachable"] == 0.0


@patch("app.observation_engine.adapters.scheduler.SessionLocal", side_effect=RuntimeError("db down"))
def test_scheduler_adapter_degrades_gracefully_on_db_failure(_mock) -> None:
    rec = SchedulerAdapter().collect()[0]
    assert rec.health is ObservationHealth.UNKNOWN
    assert rec.metrics["reachable"] == 0.0


@patch("app.observation_engine.adapters.telegram.SessionLocal", side_effect=RuntimeError("db down"))
def test_telegram_adapter_degrades_gracefully_on_db_failure(_mock) -> None:
    rec = TelegramAdapter().collect()[0]
    assert rec.health is ObservationHealth.UNKNOWN
    assert rec.metrics["reachable"] == 0.0


# ── WS6: engine-level error handling never cancels the snapshot ─────────────

def test_collect_all_records_adapter_failure_instead_of_dropping_it() -> None:
    class BoomAdapter:
        adapter_name = "boom"
        project = "test"
        domain = "GENERIC"

        def collect(self):
            raise RuntimeError("simulated adapter crash")

        def health(self):
            return {"status": "UNKNOWN", "adapter": "boom"}

    engine = ObservationEngine()
    engine._adapters = [BoomAdapter()]
    records = engine.collect_all()
    assert len(records) == 1
    assert records[0].source == "boom-collection-error"
    assert records[0].health is ObservationHealth.UNKNOWN
    assert records[0].severity is ObservationSeverity.ERROR
    assert "simulated adapter crash" in records[0].evidence[0]


def test_collect_all_continues_after_one_adapter_fails() -> None:
    class BoomAdapter:
        adapter_name = "boom"
        project = "test"
        domain = "GENERIC"

        def collect(self):
            raise RuntimeError("boom")

        def health(self):
            return {}

    engine = ObservationEngine()
    engine._adapters = [BoomAdapter(), PostgresAdapter()]
    records = engine.collect_all()
    sources = [r.source for r in records]
    assert "boom-collection-error" in sources
    assert "postgresql" in sources  # the healthy adapter still ran
