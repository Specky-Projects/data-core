import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database.models import Base


class SportsBook(Base):
    __tablename__ = "sportsbooks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    base_url: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    markets: Mapped[list["SportsMarket"]] = relationship(back_populates="bookmaker")
    raw_payloads: Mapped[list["SportsRawPayload"]] = relationship(back_populates="sportsbook")


class SportsLeague(Base):
    __tablename__ = "sports_leagues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sport: Mapped[str] = mapped_column(String(80), index=True)
    league_name: Mapped[str] = mapped_column(String(120), index=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    events: Mapped[list["SportsEvent"]] = relationship(back_populates="league")

    __table_args__ = (UniqueConstraint("sport", "league_name", "country", name="uq_sports_league_identity"),)


class SportsEvent(Base):
    __tablename__ = "sports_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    league_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sports_leagues.id"), index=True)
    home_team: Mapped[str] = mapped_column(String(160), index=True)
    away_team: Mapped[str] = mapped_column(String(160), index=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    event_status: Mapped[str] = mapped_column(String(40), default="scheduled", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    league: Mapped[SportsLeague] = relationship(back_populates="events")
    markets: Mapped[list["SportsMarket"]] = relationship(back_populates="event")

    __table_args__ = (
        UniqueConstraint("league_id", "external_id", name="uq_sports_event_league_external"),
        Index("ix_sports_event_matchup_start", "home_team", "away_team", "start_time"),
    )


class SportsMarket(Base):
    __tablename__ = "sports_markets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sports_events.id"), index=True)
    market_type: Mapped[str] = mapped_column(String(80), index=True)
    selection: Mapped[str] = mapped_column(String(160), index=True)
    handicap: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    bookmaker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sportsbooks.id"), index=True)

    event: Mapped[SportsEvent] = relationship(back_populates="markets")
    bookmaker: Mapped[SportsBook] = relationship(back_populates="markets")
    snapshots: Mapped[list["SportsOddsSnapshot"]] = relationship(back_populates="market")

    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "bookmaker_id",
            "market_type",
            "selection",
            "handicap",
            name="uq_sports_market_identity",
        ),
    )


class SportsOddsSnapshot(Base):
    __tablename__ = "sports_odds_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sports_markets.id"), index=True)
    odd: Mapped[float] = mapped_column(Numeric(10, 4))
    implied_probability: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    market: Mapped[SportsMarket] = relationship(back_populates="snapshots")

    __table_args__ = (Index("ix_sports_odds_market_collected", "market_id", "collected_at"),)


class SportsRawPayload(Base):
    __tablename__ = "sports_raw_payloads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sportsbook_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sportsbooks.id"), index=True)
    endpoint: Mapped[str] = mapped_column(Text)
    payload: Mapped[str] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    sportsbook: Mapped[SportsBook] = relationship(back_populates="raw_payloads")
