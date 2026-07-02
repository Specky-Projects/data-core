"""Tests for the Universal Platform status router — public, advisory-only."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.universal_platform import bootstrap
from app.universal_platform.api import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    bootstrap.reset_for_tests()


def teardown_function() -> None:
    bootstrap.reset_for_tests()


def test_status_endpoint_returns_initialized_platform() -> None:
    resp = _client().get("/universal-platform/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["initialized"] is True
    assert body["advisory_only"] is True


def test_status_endpoint_never_errors_on_construction_failure(monkeypatch) -> None:
    from unittest.mock import patch

    with patch("app.universal_platform.bootstrap.Phase2Platform", side_effect=RuntimeError("boom")):
        resp = _client().get("/universal-platform/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["initialized"] is False
    assert body["error"] == "boom"


def test_status_endpoint_not_in_public_schema() -> None:
    app = FastAPI()
    app.include_router(router)
    paths = app.openapi()["paths"]
    assert "/universal-platform/status" not in paths


# ── read-only aggregate views (daily-brief, alerts) ─────────────────────────

_CRITICAL_INFRA_EVENT = {
    "project": "infrastructure",
    "component": "postgres",
    "event_type": "postgres.down",
    "service": "pg1",
    "occurred_at": "2026-06-30T10:00:00Z",
}


def test_daily_brief_empty_is_wellformed() -> None:
    resp = _client().get("/universal-platform/daily-brief")
    assert resp.status_code == 200
    body = resp.json()
    assert body["initialized"] is True
    assert body["advisory_only"] is True
    assert isinstance(body["sections"], list)
    assert "scientific_health" in body


def test_alerts_empty_is_wellformed() -> None:
    resp = _client().get("/universal-platform/alerts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["initialized"] is True
    assert body["advisory_only"] is True
    assert body["alerts"] == []
    assert body["count"] == 0


def test_daily_brief_with_events_reuses_builder() -> None:
    resp = _client().request(
        "GET",
        "/universal-platform/daily-brief",
        json={"events": [_CRITICAL_INFRA_EVENT], "generated_at": "2026-06-30"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["initialized"] is True
    assert body["generated_at"] == "2026-06-30"
    assert len(body["sections"]) > 0


def test_alerts_with_events_reuses_engine() -> None:
    resp = _client().request(
        "GET",
        "/universal-platform/alerts",
        json={"events": [_CRITICAL_INFRA_EVENT]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    alert = body["alerts"][0]
    assert alert["severity"] == "CRITICAL"
    for key in ("alert_id", "root_cause", "recommended_action", "replay_ref"):
        assert key in alert


def test_aggregate_routes_never_error_on_construction_failure() -> None:
    from unittest.mock import patch

    with patch("app.universal_platform.bootstrap.Phase2Platform", side_effect=RuntimeError("boom")):
        client = _client()
        brief = client.get("/universal-platform/daily-brief")
        alerts = client.get("/universal-platform/alerts")
    assert brief.status_code == 200
    assert brief.json()["initialized"] is False
    assert brief.json()["advisory_only"] is True
    assert alerts.status_code == 200
    assert alerts.json()["initialized"] is False
    assert alerts.json()["count"] == 0


def test_aggregate_routes_not_in_public_schema() -> None:
    app = FastAPI()
    app.include_router(router)
    paths = app.openapi()["paths"]
    assert "/universal-platform/daily-brief" not in paths
    assert "/universal-platform/alerts" not in paths
