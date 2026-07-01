"""Integration tests for the Observer Framework production pipeline.

Uses the shared `db_session` fixture (real Postgres via SAVEPOINT rollback,
see tests/conftest.py) — skips automatically if no local test DB is
available, exactly like every other DB-backed test in this repo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.observer_framework.models import ObserverSnapshotRun  # noqa: E402
from app.observer_framework.pipeline import run_observer_cycle, run_summary_dict  # noqa: E402


@pytest.fixture(autouse=True)
def _ensure_table(db_session):
    ObserverSnapshotRun.metadata.create_all(
        bind=db_session.get_bind(), tables=[ObserverSnapshotRun.__table__], checkfirst=True
    )


def test_first_cycle_persists_a_row(db_session) -> None:
    run = run_observer_cycle(db_session, send_telegram=False)

    assert run.id is not None
    assert run.classification in ("GO", "GO_WITH_OBSERVATIONS", "NO_GO")
    assert 0.0 <= run.operational_score <= 100.0
    assert run.snapshot_json["schema_version"]
    assert run.diagnosis_json["snapshot_id"] == run.snapshot_id
    assert run.telegram_sent is False  # send_telegram=False


def test_first_cycle_compares_snapshot_against_itself(db_session) -> None:
    """With no prior history, the pipeline must not crash — it treats the
    first snapshot as its own baseline (zero new incidents by construction)."""
    run = run_observer_cycle(db_session, send_telegram=False)

    assert run.new_incident_count == 0
    assert run.validation_json["before_snapshot_id"] == run.validation_json["after_snapshot_id"]


def test_second_cycle_reads_previous_row_from_history(db_session) -> None:
    first = run_observer_cycle(db_session, send_telegram=False)
    second = run_observer_cycle(db_session, send_telegram=False)

    assert second.id != first.id
    assert second.validation_json["before_snapshot_id"] == first.snapshot_id
    assert second.validation_json["after_snapshot_id"] == second.snapshot_id


def test_run_summary_dict_excludes_raw_snapshot(db_session) -> None:
    run = run_observer_cycle(db_session, send_telegram=False)
    summary = run_summary_dict(run)

    assert "snapshot_json" not in summary
    assert "diagnosis_json" not in summary
    assert summary["classification"] == run.classification
    assert summary["operational_score"] == run.operational_score
