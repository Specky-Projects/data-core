"""Tests for the read-only Capability Registry HTTP projection.

These assert the projection reflects the *existing* registry populated by the
real bootstraps — no fixtures fake the registrations, so the test also proves
the bootstraps are importable and produce advisory-only capabilities.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.capability_orchestrator.api import _load_registrations, router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_bootstraps_populate_registrations() -> None:
    regs = _load_registrations()
    assert regs, "expected the existing bootstraps to register capabilities"
    # Every registration must be advisory-only (enforced by the contract).
    assert all(reg.advisory_only for _, reg in regs)


def test_list_capabilities_projects_registry() -> None:
    client = _client()
    resp = client.get("/capabilities")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == len(body["capabilities"]) > 0
    assert body["advisory_only"] is True
    # kinds histogram sums to total.
    assert sum(body["kinds"].values()) == body["total"]
    # Each item carries the projected fields (no schema mutation).
    sample = body["capabilities"][0]
    for field in ("capability_id", "kind", "owner", "advisory_only", "source_platform"):
        assert field in sample


def test_get_capability_by_id_and_404() -> None:
    client = _client()
    known = client.get("/capabilities").json()["capabilities"][0]["capability_id"]
    ok = client.get(f"/capabilities/{known}")
    assert ok.status_code == 200
    assert ok.json()["capability_id"] == known

    missing = client.get("/capabilities/does.not.exist")
    assert missing.status_code == 404


def test_filter_by_kind() -> None:
    client = _client()
    all_items = client.get("/capabilities").json()["capabilities"]
    some_kind = all_items[0]["kind"]
    resp = client.get(f"/capabilities/kind/{some_kind}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == some_kind
    assert body["total"] > 0
    assert all(item["kind"] == some_kind for item in body["capabilities"])

    bad = client.get("/capabilities/kind/not-a-kind")
    assert bad.status_code == 404
