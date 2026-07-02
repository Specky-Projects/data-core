"""Read-only dashboard endpoints for the Poupi Baby opportunity bridge."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.business_os.poupi_baby_bridge.service import PoupiBabyOpportunityBridge

router = APIRouter(
    prefix="/business-os/poupi-baby/opportunities",
    tags=["business-os", "poupi-baby"],
)


@router.get("")
def list_opportunities(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    rows = PoupiBabyOpportunityBridge().list_recent(limit)
    return {
        "source": "poupi-baby",
        "domain": "AFFILIATE",
        "count": len(rows),
        "items": rows,
    }


@router.get("/latest")
def latest_opportunity() -> dict:
    rows = PoupiBabyOpportunityBridge().list_recent(1)
    return {
        "source": "poupi-baby",
        "domain": "AFFILIATE",
        "item": rows[0] if rows else None,
    }
