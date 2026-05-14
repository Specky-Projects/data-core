import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database.models import Base


class RealEstateSource(Base):
    __tablename__ = "real_estate_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    base_url: Mapped[str] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    listings: Mapped[list["RealEstateListing"]] = relationship(back_populates="source")


class RealEstateListing(Base):
    __tablename__ = "real_estate_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("real_estate_sources.id"), index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    property_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    purpose: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    neighborhood: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parking_spaces: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area_m2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    condo_fee: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    iptu: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[RealEstateSource] = relationship(back_populates="listings")
    price_history: Mapped[list["RealEstatePriceHistory"]] = relationship(back_populates="listing")
    raw_pages: Mapped[list["RealEstateRawPage"]] = relationship(back_populates="listing")

    __table_args__ = (
        UniqueConstraint("source_id", "url", name="uq_real_estate_listing_source_url"),
        UniqueConstraint("source_id", "external_id", name="uq_real_estate_listing_source_external"),
        Index("ix_real_estate_listing_city_neighborhood", "city", "neighborhood"),
    )


class RealEstatePriceHistory(Base):
    __tablename__ = "real_estate_price_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("real_estate_listings.id"), index=True
    )
    price: Mapped[float] = mapped_column(Numeric(14, 2))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    listing: Mapped[RealEstateListing] = relationship(back_populates="price_history")

    __table_args__ = (Index("ix_real_estate_price_listing_collected", "listing_id", "collected_at"),)


class RealEstateRawPage(Base):
    __tablename__ = "real_estate_raw_pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("real_estate_listings.id"), nullable=True, index=True
    )
    url: Mapped[str] = mapped_column(Text, index=True)
    html: Mapped[str] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    listing: Mapped[RealEstateListing | None] = relationship(back_populates="raw_pages")

