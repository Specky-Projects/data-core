from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.business_os.poupi_baby_bridge.api import router
from app.business_os.poupi_baby_bridge.service import PoupiBabyOpportunityBridge
from app.business_os.poupi_baby_bridge.storage import JsonlOpportunityEvidenceRegistry


def _runtime_payload() -> dict:
    return {
        "offerId": "offer-001",
        "productId": "prod-001",
        "productTitle": "Pampers Confort Sec XG 92 unidades",
        "productUrl": "https://www.paguemenos.com.br/fralda/p",
        "affiliateUrl": "https://www.paguemenos.com.br/fralda/p?utm_source=poupi",
        "marketplace": "Pague Menos",
        "category": "Fraldas",
        "dealScore": 78,
        "dealLabel": "Otima oferta",
        "telegramStatus": "dry_run",
        "siteStatus": "planned",
        "dryRun": True,
        "publishedAt": "2026-07-01T12:00:00Z",
    }


def test_bridge_emits_affiliate_opportunity_and_persists_cycle(tmp_path) -> None:
    registry = JsonlOpportunityEvidenceRegistry(tmp_path / "registry.jsonl")
    bridge = PoupiBabyOpportunityBridge(registry)

    record = bridge.emit(_runtime_payload())

    assert record["domain"] == "AFFILIATE"
    assert record["opportunity"]["opportunity_id"] == "offer-001"
    assert record["opportunity"]["confidence"] == 0.78
    assert record["references"]["evaluation_bundle"].startswith("eval:")
    assert record["references"]["ranking_score"].startswith("rank:")
    assert record["references"]["business_snapshot"].startswith("snap:")
    assert record["references"]["replay"]
    assert record["references"]["explainability"]
    assert record["references"]["audit_snapshot"]
    assert record["channels"] == {
        "planned": ["site", "telegram"],
        "site": "planned",
        "telegram": "dry_run",
        "dry_run": True,
    }

    rows = registry.list_recent()
    assert len(rows) == 1
    assert rows[0]["raw_payload"]["affiliateUrl"].endswith("utm_source=poupi")


def test_read_only_dashboard_lists_persisted_opportunities(tmp_path, monkeypatch) -> None:
    registry_path = tmp_path / "registry.jsonl"
    monkeypatch.setenv("POUPI_BABY_OPPORTUNITY_REGISTRY_PATH", str(registry_path))
    PoupiBabyOpportunityBridge(JsonlOpportunityEvidenceRegistry(registry_path)).emit(
        _runtime_payload()
    )

    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/business-os/poupi-baby/opportunities")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["domain"] == "AFFILIATE"
