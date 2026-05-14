from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from api.deps import db_session
from app.modules.real_estate.models import RealEstateListing, RealEstatePriceHistory, RealEstateSource
from app.modules.real_estate.services import RealEstateService

router = APIRouter(prefix="/api/v1/real-estate", tags=["real-estate"])


class RealEstateSourceResponse(BaseModel):
    id: UUID
    name: str
    base_url: str
    city: str | None
    state: str | None
    active: bool

    model_config = ConfigDict(from_attributes=True)


class RealEstateListingResponse(BaseModel):
    id: UUID
    source_id: UUID
    external_id: str | None
    url: str
    title: str | None
    property_type: str | None
    purpose: str | None
    city: str | None
    neighborhood: str | None
    address: str | None
    bedrooms: int | None
    bathrooms: int | None
    parking_spaces: int | None
    area_m2: int | None
    condo_fee: float | None
    iptu: float | None
    active: bool
    first_seen_at: Any
    last_seen_at: Any

    model_config = ConfigDict(from_attributes=True)


class RealEstatePriceHistoryResponse(BaseModel):
    id: UUID
    listing_id: UUID
    price: float
    collected_at: Any

    model_config = ConfigDict(from_attributes=True)


@router.get("/listings", response_model=list[RealEstateListingResponse])
def list_listings(
    db: Session = Depends(db_session),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    city: str | None = None,
) -> list[RealEstateListing]:
    return RealEstateService(db).list_listings(limit=limit, offset=offset, city=city)


@router.get("/listings/{listing_id}", response_model=RealEstateListingResponse)
def get_listing(listing_id: UUID, db: Session = Depends(db_session)) -> RealEstateListing:
    listing = RealEstateService(db).get_listing(str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


@router.get("/listings/{listing_id}/price-history", response_model=list[RealEstatePriceHistoryResponse])
def get_price_history(
    listing_id: UUID,
    db: Session = Depends(db_session),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[RealEstatePriceHistory]:
    return RealEstateService(db).price_history(str(listing_id), limit=limit)


@router.get("/sources", response_model=list[RealEstateSourceResponse])
def list_sources(db: Session = Depends(db_session)) -> list[RealEstateSource]:
    return RealEstateService(db).list_sources(active_only=False)

