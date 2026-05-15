from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.modules.sports_odds.models import (
    SportsBook,
    SportsEvent,
    SportsLeague,
    SportsMarket,
    SportsOddsSnapshot,
    SportsRawPayload,
)
from app.modules.sports_odds.parsers import ParsedOddsMarket, ParsedSportsEvent


class SportsOddsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create_sportsbook(self, *, name: str, base_url: str) -> SportsBook:
        sportsbook = self.db.query(SportsBook).filter(SportsBook.name == name).one_or_none()
        if sportsbook:
            sportsbook.base_url = base_url
            sportsbook.active = True
            self.db.flush()
            return sportsbook
        sportsbook = SportsBook(name=name, base_url=base_url, active=True)
        self.db.add(sportsbook)
        self.db.flush()
        return sportsbook

    def get_or_create_league(self, *, sport: str, league_name: str, country: str | None) -> SportsLeague:
        league = (
            self.db.query(SportsLeague)
            .filter(
                SportsLeague.sport == sport,
                SportsLeague.league_name == league_name,
                SportsLeague.country == country,
            )
            .one_or_none()
        )
        if league:
            league.active = True
            self.db.flush()
            return league
        league = SportsLeague(sport=sport, league_name=league_name, country=country, active=True)
        self.db.add(league)
        self.db.flush()
        return league

    def save_raw(self, *, sportsbook: SportsBook, endpoint: str, payload: str) -> SportsRawPayload:
        raw = SportsRawPayload(sportsbook_id=sportsbook.id, endpoint=endpoint, payload=payload)
        self.db.add(raw)
        self.db.flush()
        return raw

    def save_event(self, parsed: ParsedSportsEvent) -> SportsEvent:
        league = self.get_or_create_league(
            sport=parsed.sport,
            league_name=parsed.league_name,
            country=parsed.country,
        )
        event = None
        if parsed.external_id:
            event = (
                self.db.query(SportsEvent)
                .filter(SportsEvent.league_id == league.id, SportsEvent.external_id == parsed.external_id)
                .one_or_none()
            )
        if event is None:
            event = (
                self.db.query(SportsEvent)
                .filter(
                    SportsEvent.league_id == league.id,
                    SportsEvent.home_team == parsed.home_team,
                    SportsEvent.away_team == parsed.away_team,
                    SportsEvent.start_time == parsed.start_time,
                )
                .one_or_none()
            )

        now = datetime.now(timezone.utc)
        if event is None:
            event = SportsEvent(
                external_id=parsed.external_id,
                league_id=league.id,
                home_team=parsed.home_team,
                away_team=parsed.away_team,
                start_time=parsed.start_time,
                created_at=now,
            )
            self.db.add(event)

        event.external_id = parsed.external_id or event.external_id
        event.home_team = parsed.home_team
        event.away_team = parsed.away_team
        event.start_time = parsed.start_time
        event.event_status = parsed.event_status
        event.updated_at = now
        self.db.flush()
        return event

    def save_odds_snapshot(
        self,
        *,
        event: SportsEvent,
        sportsbook: SportsBook,
        parsed: ParsedOddsMarket,
    ) -> SportsOddsSnapshot:
        query = self.db.query(SportsMarket).filter(
            SportsMarket.event_id == event.id,
            SportsMarket.bookmaker_id == sportsbook.id,
            SportsMarket.market_type == parsed.market_type,
            SportsMarket.selection == parsed.selection,
        )
        query = query.filter(
            SportsMarket.handicap.is_(None) if parsed.handicap is None else SportsMarket.handicap == parsed.handicap
        )
        market = query.one_or_none()
        if market is None:
            market = SportsMarket(
                event_id=event.id,
                bookmaker_id=sportsbook.id,
                market_type=parsed.market_type,
                selection=parsed.selection,
                handicap=parsed.handicap,
            )
            self.db.add(market)
            self.db.flush()

        snapshot = SportsOddsSnapshot(
            market_id=market.id,
            odd=parsed.odd,
            implied_probability=(1 / parsed.odd) if parsed.odd > 0 else None,
        )
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def list_sportsbooks(self, *, active_only: bool = True) -> list[SportsBook]:
        query = self.db.query(SportsBook)
        if active_only:
            query = query.filter(SportsBook.active.is_(True))
        return query.order_by(SportsBook.name).all()

    def list_leagues(self, *, active_only: bool = True) -> list[SportsLeague]:
        query = self.db.query(SportsLeague)
        if active_only:
            query = query.filter(SportsLeague.active.is_(True))
        return query.order_by(SportsLeague.sport, SportsLeague.league_name).all()

    def list_events(
        self,
        *,
        limit: int,
        offset: int,
        league_name: str | None = None,
        status: str | None = None,
    ) -> list[SportsEvent]:
        query = self.db.query(SportsEvent).join(SportsLeague)
        if league_name:
            query = query.filter(SportsLeague.league_name.ilike(league_name))
        if status:
            query = query.filter(SportsEvent.event_status == status)
        return query.order_by(desc(SportsEvent.start_time)).offset(offset).limit(limit).all()

    def get_event(self, event_id: str) -> SportsEvent | None:
        return self.db.get(SportsEvent, event_id)

    def odds_history(self, event_id: str, *, limit: int = 500) -> list[SportsOddsSnapshot]:
        return (
            self.db.query(SportsOddsSnapshot)
            .join(SportsMarket)
            .filter(SportsMarket.event_id == event_id)
            .order_by(desc(SportsOddsSnapshot.collected_at))
            .limit(limit)
            .all()
        )
