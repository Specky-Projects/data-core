"""Tests for the Observer Framework router — mounted standalone (no auth_dep,
matching the app.include_router(..., dependencies=auth_dep) wiring's actual
route logic, not the auth layer itself, which is tested by the API-key tests
elsewhere)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.observer_framework.api import router  # noqa: E402
from app.observer_framework.models import ObserverSnapshotRun  # noqa: E402
from database.session import get_db  # noqa: E402


@pytest.fixture(autouse=True)
def _ensure_table(db_session):
    ObserverSnapshotRun.metadata.create_all(
        bind=db_session.get_bind(), tables=[ObserverSnapshotRun.__table__], checkfirst=True
    )


def _client(db_session) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_latest_with_no_runs_yet(db_session) -> None:
    resp = _client(db_session).get("/observer/latest")
    assert resp.status_code == 200
    assert resp.json() == {"status": "no_runs_yet"}


def test_history_with_no_runs_yet(db_session) -> None:
    resp = _client(db_session).get("/observer/history")
    assert resp.status_code == 200
    assert resp.json() == {"count": 0, "runs": []}


def test_run_now_persists_and_is_visible_in_latest(db_session) -> None:
    client = _client(db_session)

    run_resp = client.post("/observer/run", params={"send_telegram": False})
    assert run_resp.status_code == 200
    body = run_resp.json()
    assert "classification" in body
    assert "snapshot_json" not in body

    latest_resp = client.get("/observer/latest")
    assert latest_resp.json()["snapshot_id"] == body["snapshot_id"]


def test_snapshot_with_no_runs_yet(db_session) -> None:
    resp = _client(db_session).get("/observer/snapshot")
    assert resp.status_code == 200
    assert resp.json() == {"status": "SNAPSHOT_UNAVAILABLE", "reason": "no_runs_yet"}


def test_snapshot_returns_full_contract_after_run(db_session) -> None:
    client = _client(db_session)

    run_resp = client.post("/observer/run", params={"send_telegram": False})
    snapshot_id = run_resp.json()["snapshot_id"]

    resp = client.get("/observer/snapshot")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "OK"
    assert body["snapshot"]["snapshot_id"] == snapshot_id
    assert "diagnosis" in body and "overall_health" in body["diagnosis"]
    assert "validation" in body
    assert "certification" in body
