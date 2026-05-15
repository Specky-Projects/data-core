import logging
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.modules.real_estate.models import (
    RealEstateListing,
    RealEstatePriceHistory,
    RealEstateRawPage,
    RealEstateSource,
)
from app.modules.real_estate.parsers.generic_parser import ParsedRealEstateListing

logger = logging.getLogger(__name__)


class RealEstateService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create_source(
        self,
        *,
        name: str,
        base_url: str,
        city: str | None = None,
        state: str | None = None,
    ) -> RealEstateSource:
        source = self.db.query(RealEstateSource).filter(RealEstateSource.name == name).one_or_none()
        if source:
            source.base_url = base_url
            source.city = city or source.city
            source.state = state or source.state
            source.active = True
            self.db.flush()
            return source

        source = RealEstateSource(name=name, base_url=base_url, city=city, state=state, active=True)
        self.db.add(source)
        self.db.flush()
        return source

    def save_raw(self, *, url: str, html: str, listing: RealEstateListing | None = None) -> RealEstateRawPage:
        raw = RealEstateRawPage(listing_id=listing.id if listing else None, url=url, html=html)
        self.db.add(raw)
        self.db.flush()
        return raw

    def save_listing(
        self,
        *,
        source: RealEstateSource,
        parsed: ParsedRealEstateListing,
    ) -> RealEstateListing:
        listing = (
            self.db.query(RealEstateListing)
            .filter(RealEstateListing.source_id == source.id, RealEstateListing.url == parsed.url)
            .one_or_none()
        )
        if not listing and parsed.external_id:
            listing = (
                self.db.query(RealEstateListing)
                .filter(
                    RealEstateListing.source_id == source.id,
                    RealEstateListing.external_id == parsed.external_id,
                )
                .one_or_none()
            )

        now = datetime.now(timezone.utc)
        if not listing:
            listing = RealEstateListing(
                source_id=source.id,
                external_id=parsed.external_id,
                url=parsed.url,
                first_seen_at=now,
            )
            self.db.add(listing)

        listing.external_id = parsed.external_id or listing.external_id
        listing.url = parsed.url
        listing.title = parsed.title
        listing.property_type = parsed.property_type
        listing.purpose = parsed.purpose
        listing.city = parsed.city or source.city
        listing.neighborhood = parsed.neighborhood
        listing.address = parsed.address
        listing.bedrooms = parsed.bedrooms
        listing.bathrooms = parsed.bathrooms
        listing.parking_spaces = parsed.parking_spaces
        listing.area_m2 = parsed.area_m2
        listing.condo_fee = parsed.condo_fee
        listing.iptu = parsed.iptu
        listing.active = True
        listing.last_seen_at = now
        self.db.flush()
        return listing

    def save_price_history(
        self,
        *,
        listing: RealEstateListing,
        price: float | None,
    ) -> RealEstatePriceHistory | None:
        if price is None:
            return None
        latest = (
            self.db.query(RealEstatePriceHistory)
            .filter(RealEstatePriceHistory.listing_id == listing.id)
            .order_by(desc(RealEstatePriceHistory.collected_at))
            .first()
        )
        if latest and float(latest.price) == float(price):
            return latest

        point = RealEstatePriceHistory(listing_id=listing.id, price=price)
        self.db.add(point)
        self.db.flush()
        return point

    def list_sources(self, *, active_only: bool = True) -> list[RealEstateSource]:
        query = self.db.query(RealEstateSource)
        if active_only:
            query = query.filter(RealEstateSource.active.is_(True))
        return query.order_by(RealEstateSource.name).all()

    def list_listings(self, *, limit: int, offset: int, city: str | None = None) -> list[RealEstateListing]:
        query = self.db.query(RealEstateListing)
        if city:
            query = query.filter(RealEstateListing.city.ilike(city))
        return query.order_by(desc(RealEstateListing.last_seen_at)).offset(offset).limit(limit).all()

    def get_listing(self, listing_id: str) -> RealEstateListing | None:
        return self.db.get(RealEstateListing, listing_id)

    def price_history(self, listing_id: str, *, limit: int = 200) -> list[RealEstatePriceHistory]:
        return (
            self.db.query(RealEstatePriceHistory)
            .filter(RealEstatePriceHistory.listing_id == listing_id)
            .order_by(desc(RealEstatePriceHistory.collected_at))
            .limit(limit)
            .all()
        )

