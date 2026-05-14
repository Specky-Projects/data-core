from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from api.deps import db_session
from app.modules.sports_odds.models import SportsBook, SportsEvent, SportsLeague, SportsOddsSnapshot
from app.modules.sports_odds.services import SportsOddsService

router = APIRouter(prefix="/api/v1/sports-odds", tags=["sports-odds"])


class SportsBookResponse(BaseModel):
    id: UUID
    name: str
    base_url: str
    active: bool

    model_config = ConfigDict(from_attributes=True)


class SportsLeagueResponse(BaseModel):
    id: UUID
    sport: str
    league_name: str
    country: str | None
    active: bool

    model_config = ConfigDict(from_attributes=True)


class SportsEventResponse(BaseModel):
    id: UUID
    external_id: str | None
    league_id: UUID
    home_team: str
    away_team: str
    start_time: Any
    event_status: str
    created_at: Any
    updated_at: Any

    model_config = ConfigDict(from_attributes=True)


class SportsOddsSnapshotResponse(BaseModel):
    id: UUID
    market_id: UUID
    odd: float
    implied_probability: float | None
    collected_at: Any

    model_config = ConfigDict(from_attributes=True)


@router.get("/events", response_model=list[SportsEventResponse])
def list_events(
    db: Session = Depends(db_session),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    league_name: str | None = None,
    status: str | None = None,
) -> list[SportsEvent]:
    return SportsOddsService(db).list_events(limit=limit, offset=offset, league_name=league_name, status=status)


@router.get("/events/{event_id}", response_model=SportsEventResponse)
def get_event(event_id: UUID, db: Session = Depends(db_session)) -> SportsEvent:
    event = SportsOddsService(db).get_event(str(event_id))
    if not event:
        raise HTTPException(status_code=404, detail="Sports event not found")
    return event


@router.get("/events/{event_id}/odds-history", response_model=list[SportsOddsSnapshotResponse])
def get_odds_history(
    event_id: UUID,
    db: Session = Depends(db_session),
    limit: int = Query(default=500, ge=1, le=2000),
) -> list[SportsOddsSnapshot]:
    return SportsOddsService(db).odds_history(str(event_id), limit=limit)


@router.get("/sportsbooks", response_model=list[SportsBookResponse])
def list_sportsbooks(db: Session = Depends(db_session)) -> list[SportsBook]:
    return SportsOddsService(db).list_sportsbooks(active_only=False)


@router.get("/leagues", response_model=list[SportsLeagueResponse])
def list_leagues(db: Session = Depends(db_session)) -> list[SportsLeague]:
    return SportsOddsService(db).list_leagues(active_only=False)
