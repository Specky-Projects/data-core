"""
NBA odds ingestion — The Odds API v4.

Source: https://api.the-odds-api.com/v4/
Env var: THE_ODDS_API_KEY

Free tier (500 req/month):
  - Upcoming games only: GET /sports/basketball_nba/odds
  - No historical access

Paid tier (history):
  - Historical snapshot: GET /historical/sports/basketball_nba/odds?date={iso8601}
  - Required for backfill of 2022-2024 seasons

BLOCKED states are returned as OddsCollectResult with blocked=True so callers
can classify them without exceptions.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.modules.nba.quant.models import MarketType, NbaGame, NbaOdds

logger = logging.getLogger(__name__)

_API_KEY = os.environ.get("THE_ODDS_API_KEY", "")
_BASE_URL = "https://api.the-odds-api.com/v4"
_SPORT = "basketball_nba"
_REGIONS = "us"
_MARKETS = "h2h,spreads,totals"
_ODDS_FORMAT = "american"
_REQUEST_DELAY = 0.5   # stay well below rate limits

# Fuzzy team name aliases — The Odds API vs ESPN naming
_TEAM_ALIASES: dict[str, str] = {
    # The Odds API sometimes uses these variants
    "LA Clippers": "LA Clippers",
    "Los Angeles Clippers": "LA Clippers",
    "New Orleans Pelicans": "New Orleans Pelicans",
    "Portland Trail Blazers": "Portland Trail Blazers",
    "Oklahoma City Thunder": "Oklahoma City Thunder",
    "Golden State Warriors": "Golden State Warriors",
}


def _normalize_team(name: str) -> str:
    return _TEAM_ALIASES.get(name, name)


@dataclass
class OddsCollectResult:
    games_matched: int = 0
    odds_upserted: int = 0
    games_unmatched: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    blocked: bool = False
    blocked_reason: str = ""
    requests_remaining: int | None = None

    @property
    def ok(self) -> bool:
        return not self.blocked and len(self.errors) == 0


def _check_api_key() -> OddsCollectResult | None:
    """Return a blocked result if API key is missing, else None."""
    if not _API_KEY:
        return OddsCollectResult(
            blocked=True,
            blocked_reason=(
                "THE_ODDS_API_KEY not set. "
                "Set this env var in Coolify and redeploy. "
                "Free tier: 500 req/month, upcoming games only. "
                "Paid tier: historical endpoint for 2022-2024 backfill."
            ),
        )
    return None


def _upsert_odds(
    db: Session,
    *,
    game_id: object,
    bookmaker: str,
    market_type: MarketType,
    selection: str,
    line: float | None,
    odd: float,
) -> NbaOdds:
    existing = (
        db.query(NbaOdds)
        .filter(
            NbaOdds.game_id == game_id,
            NbaOdds.bookmaker == bookmaker,
            NbaOdds.market_type == market_type,
            NbaOdds.selection == selection,
        )
        .first()
    )
    if existing:
        existing.line = line
        existing.odd = odd
        return existing
    record = NbaOdds(
        game_id=game_id,
        bookmaker=bookmaker,
        market_type=market_type,
        selection=selection,
        line=line,
        odd=odd,
    )
    db.add(record)
    return record


def _match_game(db: Session, home_team: str, away_team: str, commence_time: str) -> NbaGame | None:
    """
    Match an Odds API event to an NbaGame row.
    Matches on: (home_team, away_team, game_date within ±1 day).
    """
    try:
        event_dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
    except ValueError:
        return None

    home_norm = _normalize_team(home_team)
    away_norm = _normalize_team(away_team)
    window_start = event_dt - timedelta(hours=12)
    window_end = event_dt + timedelta(hours=12)

    game = (
        db.query(NbaGame)
        .filter(
            NbaGame.home_team == home_norm,
            NbaGame.away_team == away_norm,
            NbaGame.game_date >= window_start,
            NbaGame.game_date <= window_end,
        )
        .first()
    )
    return game


def _process_event(db: Session, event: dict, result: OddsCollectResult) -> None:
    """Parse one Odds API event and upsert its odds into nba_odds."""
    home_team = _normalize_team(event.get("home_team", ""))
    away_team = _normalize_team(event.get("away_team", ""))
    commence_time = event.get("commence_time", "")

    game = _match_game(db, home_team, away_team, commence_time)
    if not game:
        result.games_unmatched.append(f"{away_team} @ {home_team} {commence_time}")
        return

    result.games_matched += 1

    for bookmaker in event.get("bookmakers", []):
        bk_key = bookmaker.get("key", "unknown")
        for market in bookmaker.get("markets", []):
            market_key = market.get("key", "")

            if market_key == "h2h":
                mtype = MarketType.moneyline
            elif market_key == "spreads":
                mtype = MarketType.spread
            elif market_key == "totals":
                mtype = MarketType.totals
            else:
                continue

            for outcome in market.get("outcomes", []):
                selection = outcome.get("name", "")
                price = outcome.get("price")
                point = outcome.get("point")  # line (spread/total)
                if price is None:
                    continue
                try:
                    odd_val = float(price)
                    line_val = float(point) if point is not None else None
                except (TypeError, ValueError):
                    continue

                _upsert_odds(
                    db,
                    game_id=game.id,
                    bookmaker=bk_key,
                    market_type=mtype,
                    selection=selection,
                    line=line_val,
                    odd=odd_val,
                )
                result.odds_upserted += 1


def fetch_upcoming_odds(db: Session) -> OddsCollectResult:
    """
    Fetch odds for all upcoming NBA games from The Odds API free tier.
    Populates nba_odds for unstarted / future games.
    No historical access — only games with commence_time in the future.
    """
    blocked = _check_api_key()
    if blocked:
        return blocked

    result = OddsCollectResult()

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

            # Capture remaining requests from headers
            remaining = resp.headers.get("x-requests-remaining")
            if remaining:
                try:
                    result.requests_remaining = int(remaining)
                except ValueError:
                    pass

            resp.raise_for_status()
            events = resp.json()

        for event in events:
            _process_event(db, event, result)

        db.commit()
        logger.info(
            "Odds upcoming fetch done",
            extra={
                "matched": result.games_matched,
                "upserted": result.odds_upserted,
                "unmatched": len(result.games_unmatched),
                "requests_remaining": result.requests_remaining,
            },
        )

    except httpx.HTTPStatusError as exc:
        msg = f"Odds API HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        result.errors.append(msg)
        logger.error("fetch_upcoming_odds error: %s", msg)

    except Exception as exc:
        result.errors.append(str(exc))
        logger.error("fetch_upcoming_odds error: %s", exc)

    return result


def fetch_historical_odds(db: Session, game_date: datetime) -> OddsCollectResult:
    """
    Fetch historical odds snapshot for a specific date.

    Requires a paid The Odds API plan with history access.
    Endpoint: GET /historical/sports/{sport}/odds?date={iso8601}

    date: ISO 8601 datetime (e.g. 2023-10-24T18:00:00Z) — snapshot at that time.
    """
    blocked = _check_api_key()
    if blocked:
        return blocked

    result = OddsCollectResult()
    date_str = game_date.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                f"{_BASE_URL}/historical/sports/{_SPORT}/odds",
                params={
                    "apiKey": _API_KEY,
                    "date": date_str,
                    "regions": _REGIONS,
                    "markets": _MARKETS,
                    "oddsFormat": _ODDS_FORMAT,
                },
            )

            remaining = resp.headers.get("x-requests-remaining")
            if remaining:
                try:
                    result.requests_remaining = int(remaining)
                except ValueError:
                    pass

            if resp.status_code == 422:
                result.blocked = True
                result.blocked_reason = (
                    "Historical endpoint returned 422 — paid plan with "
                    "history access required. Upgrade THE_ODDS_API plan."
                )
                return result

            resp.raise_for_status()
            data = resp.json()
            events = data.get("data", data) if isinstance(data, dict) else data

        for event in events:
            _process_event(db, event, result)

        db.commit()
        time.sleep(_REQUEST_DELAY)

        logger.info(
            "Odds historical fetch done",
            extra={
                "date": date_str,
                "matched": result.games_matched,
                "upserted": result.odds_upserted,
            },
        )

    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code == 401:
            result.blocked = True
            result.blocked_reason = "THE_ODDS_API_KEY invalid or expired."
        elif code == 403:
            result.blocked = True
            result.blocked_reason = (
                "403 Forbidden — historical endpoint requires paid plan."
            )
        else:
            result.errors.append(f"HTTP {code}: {exc.response.text[:200]}")

    except Exception as exc:
        result.errors.append(str(exc))
        logger.error("fetch_historical_odds error: %s", exc)

    return result


def backfill_odds_for_seasons(
    db: Session,
    seasons: list[int],
    *,
    sample_hour: int = 18,
) -> OddsCollectResult:
    """
    Fetch historical odds for each game day in the given seasons.
    Makes one API request per unique game date.

    Requires paid The Odds API plan — will return blocked=True on free tier.

    Args:
        db: SQLAlchemy session
        seasons: list of season start years (e.g. [2022, 2023, 2024])
        sample_hour: UTC hour to snapshot odds (default 18:00 UTC = ~2pm ET)
    """
    blocked = _check_api_key()
    if blocked:
        return blocked

    agg = OddsCollectResult()

    for season in seasons:
        # Get all unique game dates for this season
        from sqlalchemy import func

        dates = (
            db.query(func.date_trunc("day", NbaGame.game_date).label("d"))
            .filter(NbaGame.season == season)
            .distinct()
            .order_by("d")
            .all()
        )

        logger.info(
            "Backfilling odds for season",
            extra={"season": season, "days": len(dates)},
        )

        for (game_day,) in dates:
            # Snapshot at sample_hour UTC on that game day
            snapshot_dt = game_day.replace(
                hour=sample_hour, minute=0, second=0, tzinfo=timezone.utc
            )
            r = fetch_historical_odds(db, snapshot_dt)
            agg.games_matched += r.games_matched
            agg.odds_upserted += r.odds_upserted
            agg.games_unmatched.extend(r.games_unmatched[:5])  # cap noise
            agg.errors.extend(r.errors)
            if r.requests_remaining is not None:
                agg.requests_remaining = r.requests_remaining

            if r.blocked:
                agg.blocked = True
                agg.blocked_reason = r.blocked_reason
                return agg  # abort early on plan error

    return agg
