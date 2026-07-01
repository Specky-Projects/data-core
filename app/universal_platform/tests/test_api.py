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
