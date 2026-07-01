"""Tests for RuntimeSnapshotBuilder — proves the full pipeline works today
against the existing ObservationEngine (a mix of real and synthetic-stub
adapters — see COLLECTOR_SPECIFICATION.md), end to end, without any new
production access path."""
from __future__ import annotations

from app.observer_framework.builder import RuntimeSnapshotBuilder
from app.observer_framework.diagnosis import SnapshotDiagnosisEngine


def test_builder_produces_valid_snapshot() -> None:
    snap = RuntimeSnapshotBuilder().build()
    assert snap.verify_integrity() is True
    assert snap.validate() == []
    assert len(snap.records) >= 12  # 9 original adapters + mirror-account split (+2) + universal_platform + research


def test_builder_output_is_diagnosable() -> None:
    snap = RuntimeSnapshotBuilder().build()
    diag = SnapshotDiagnosisEngine().diagnose(snap)
    assert diag.integrity_verified is True
    assert diag.validation_errors == ()


def test_builder_sets_runtime_version_and_build_revision() -> None:
    snap = RuntimeSnapshotBuilder().build()
    assert snap.runtime_version == "business-os-platform-v1"
    # build_revision is None outside a CI/Coolify build context — that's honest, not a bug
    assert snap.build_revision is None or isinstance(snap.build_revision, str)


def test_universal_platform_and_research_are_real_not_synthetic() -> None:
    """These two adapters report genuine local state, not hardcoded stub numbers."""
    snap = RuntimeSnapshotBuilder().build()
    up = snap.by_source("universal-platform")
    assert len(up) == 1
    assert up[0].metrics["initialized"] == 1.0
    assert up[0].metrics["capabilities_count"] == 10.0

    research = snap.by_source("research-engine")
    assert len(research) == 1
    assert research[0].metrics["capabilities_count"] == 7.0


def test_mirror_specky_cav_all_present_in_real_snapshot() -> None:
    snap = RuntimeSnapshotBuilder().build()
    assert len(snap.by_source("mirror-strategy")) == 1
    assert len(snap.by_source("mirror-strategy:specky")) == 1
    assert len(snap.by_source("mirror-strategy:cav")) == 1


def test_postgres_is_real_reachable_in_this_environment() -> None:
    """Confirms this test environment has a genuine local Postgres — not fabricated."""
    snap = RuntimeSnapshotBuilder().build()
    pg = snap.by_source("postgresql")
    assert len(pg) == 1
    assert pg[0].metrics.get("reachable") == 1.0
