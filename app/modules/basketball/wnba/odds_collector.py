"""
WNBA odds ingestion — The Odds API v4.

Sport key: basketball_wnba
Env var: THE_ODDS_API_KEY

Free tier (500 req/month): upcoming games only.
Paid tier: historical snapshots.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.modules.basketball.shared.enums import MarketType
from app.modules.basketball.wnba.models import WnbaGame, WnbaOdds

logger = logging.getLogger(__name__)

_API_KEY = os.environ.get("THE_ODDS_API_KEY", "")
_BASE_URL = "https://api.the-odds-api.com/v4"
_SPORT = "basketball_wnba"
_REGIONS = "us"
_MARKETS = "h2h,spreads,totals"
_ODDS_FORMAT = "american"
_REQUEST_DELAY = 0.5


@dataclass
class OddsCollectResult:
    games_matched: int = 0
    odds_upserted: int = 0
    games_unmatched: list[str] = field(default_factory=list)
    blocked: bool = False
    blocked_reason: str = ""
    requests_remaining: int | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blocked and not self.errors


def _normalize_team(name: str) -> str:
    return name.strip().lower()


def _match_game(db: Session, home_raw: str, away_raw: str, commence_time: str) -> WnbaGame | None:
    try:
        ct = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
    except ValueError:
        return None

    games = (
        db.query(WnbaGame)
        .filter(
            WnbaGame.game_date >= ct.replace(hour=0, minute=0, second=0),
            WnbaGame.game_date <= ct.replace(hour=23, minute=59, second=59),
        )
        .all()
    )
    home_norm = _normalize_team(home_raw)
    away_norm = _normalize_team(away_raw)

    for g in games:
        if _normalize_team(g.home_team) == home_norm and _normalize_team(g.away_team) == away_norm:
            return g
    return None


def _upsert_odds(
    db: Session,
    game: WnbaGame,
    bookmaker: str,
    market_type: MarketType,
    selection: str,
    line: float | None,
    odd: float,
) -> bool:
    existing = (
        db.query(WnbaOdds)
        .filter(
            WnbaOdds.game_id == game.id,
            WnbaOdds.bookmaker == bookmaker,
            WnbaOdds.market_type == market_type,
            WnbaOdds.selection == selection,
        )
        .first()
    )
    if existing:
        existing.line = line
        existing.odd = odd
        existing.collected_at = datetime.now(timezone.utc)
        return False
    db.add(
        WnbaOdds(
            game_id=game.id,
            bookmaker=bookmaker,
            market_type=market_type,
            selection=selection,
            line=line,
            odd=odd,
        )
    )
    return True


def fetch_upcoming_odds(db: Session) -> OddsCollectResult:
    result = OddsCollectResult()

    if not _API_KEY:
        result.blocked = True
        result.blocked_reason = "THE_ODDS_API_KEY not set"
        return result

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                f"{_BASE_URL}/sports/{_SPORT}/odds",
                params={
                    "apiKey": _API_KEY,
                    "regions": _REGIONS,
                    "markets": _MARKETS,
                    "oddsFormat": _ODDS_FORMAT,
                },
            )
            result.requests_remaining = int(resp.headers.get("x-requests-remaining", -1))

            if resp.status_code == 401:
                result.blocked = True
                result.blocked_reason = "API key invalid"
                return result
            if resp.status_code == 422:
                result.blocked = True
                result.blocked_reason = "Free tier: historical not available"
                return result
            resp.raise_for_status()

            events = resp.json()

    except Exception as exc:
        result.errors.append(str(exc))
        return result

    batch_upserted = 0
    for event in events:
        home_raw = event.get("home_team", "")
        away_raw = event.get("away_team", "")
        commence_time = event.get("commence_time", "")

        game = _match_game(db, home_raw, away_raw, commence_time)
        if not game:
            result.games_unmatched.append(f"{away_raw} @ {home_raw}")
            continue

        result.games_matched += 1

        for bookmaker_data in event.get("bookmakers", []):
            bk = bookmaker_data.get("key", "unknown")
            for market_data in bookmaker_data.get("markets", []):
                key = market_data.get("key", "")
                if key == "h2h":
                    mt = MarketType.moneyline
                elif key == "spreads":
                    mt = MarketType.spread
                elif key == "totals":
                    mt = MarketType.totals
                else:
                    continue

                for outcome in market_data.get("outcomes", []):
                    sel = outcome.get("name", "")
                    price = outcome.get("price")
                    point = outcome.get("point")
                    if price is None:
                        continue
                    new = _upsert_odds(db, game, bk, mt, sel, point, float(price))
                    if new:
                        batch_upserted += 1

        if batch_upserted >= 100:
            db.commit()
            result.odds_upserted += batch_upserted
            batch_upserted = 0

        time.sleep(_REQUEST_DELAY)

    db.commit()
    result.odds_upserted += batch_upserted
    return result
