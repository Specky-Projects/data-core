"""
NBA game data collector using Ball Don't Lie API.

Supports two tiers:
- v2 (recommended): https://api.balldontlie.io/v1/  — requires BALLDONTLIE_API_KEY
- v1 (legacy free): https://www.balldontlie.io/api/v1/ — no key, lower rate limit

Set env var BALLDONTLIE_API_KEY to enable v2.
Rate limit: 60 req/min (v1 free) / 600 req/min (v2 paid).
"""
import logging
import os
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.modules.nba.quant.models import GameStatus, NbaGame

logger = logging.getLogger(__name__)

_API_KEY = os.environ.get("BALLDONTLIE_API_KEY", "")
_BASE_URL_V2 = "https://api.balldontlie.io/v1"
_BASE_URL_V1 = "https://www.balldontlie.io/api/v1"
_BASE_URL = _BASE_URL_V2 if _API_KEY else _BASE_URL_V1
_PER_PAGE = 100
# v2 allows up to 600 req/min; v1 free tier 60 req/min
_RATE_LIMIT_DELAY = 0.12 if _API_KEY else 1.1


def _make_headers() -> dict:
    if _API_KEY:
        return {"Authorization": _API_KEY}
    return {}


def _get_json(client: httpx.Client, url: str, params: dict) -> dict:
    resp = client.get(url, params=params, headers=_make_headers(), timeout=15.0)
    resp.raise_for_status()
    return resp.json()


def _parse_game_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def _upsert_game(db: Session, raw: dict) -> NbaGame | None:
    home = raw.get("home_team", {})
    away = raw.get("visitor_team", {})
    home_name = home.get("full_name") or home.get("name")
    away_name = away.get("full_name") or away.get("name")
    if not home_name or not away_name:
        return None

    game_date = _parse_game_date(raw.get("date"))
    if not game_date:
        return None

    external_id = str(raw.get("id", ""))
    season = raw.get("season", 0)
    home_score = raw.get("home_team_score") or None
    away_score = raw.get("visitor_team_score") or None
    status_raw = str(raw.get("status", "")).lower()

    if "final" in status_raw:
        status = GameStatus.final
    elif any(kw in status_raw for kw in ("live", "in progress", "halftime", "qtr")):
        status = GameStatus.live
    else:
        status = GameStatus.scheduled

    existing = db.query(NbaGame).filter(NbaGame.external_id == external_id).first()
    if existing:
        existing.home_score = home_score
        existing.away_score = away_score
        existing.status = status
        existing.updated_at = datetime.now(timezone.utc)
        return existing

    existing_by_matchup = (
        db.query(NbaGame)
        .filter(
            NbaGame.home_team == home_name,
            NbaGame.away_team == away_name,
            NbaGame.game_date == game_date,
        )
        .first()
    )
    if existing_by_matchup:
        existing_by_matchup.external_id = external_id
        existing_by_matchup.home_score = home_score
        existing_by_matchup.away_score = away_score
        existing_by_matchup.status = status
        return existing_by_matchup

    game = NbaGame(
        external_id=external_id,
        season=season,
        game_date=game_date,
        home_team=home_name,
        away_team=away_name,
        home_score=home_score,
        away_score=away_score,
        status=status,
    )
    db.add(game)
    return game


def fetch_season(db: Session, season: int) -> int:
    """Fetch all games for a given NBA season from Ball Don't Lie API."""
    from app.modules.nba.quant.metrics import nba_q_games_collected_total

    logger.info("BDL fetch_season start", extra={"season": season, "api": "v2" if _API_KEY else "v1"})  # noqa: E501
    collected = 0
    page = 1

    with httpx.Client() as client:
        while True:
            data = _get_json(
                client,
                f"{_BASE_URL}/games",
                {"seasons[]": season, "per_page": _PER_PAGE, "page": page},
            )
            games = data.get("data", [])
            if not games:
                break

            for raw in games:
                game = _upsert_game(db, raw)
                if game:
                    collected += 1

            db.commit()

            meta = data.get("meta", {})
            total_pages = meta.get("total_pages", 1)
            if page >= total_pages:
                break

            page += 1
            time.sleep(_RATE_LIMIT_DELAY)

    nba_q_games_collected_total.labels(season=str(season)).inc(collected)
    return collected


def fetch_recent(db: Session, days_back: int = 7) -> int:
    """Fetch recent games (last N days) and update scores."""
    from datetime import timedelta

    from app.modules.nba.quant.metrics import nba_q_games_collected_total

    collected = 0
    start = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with httpx.Client() as client:
        page = 1
        while True:
            data = _get_json(
                client,
                f"{_BASE_URL}/games",
                {
                    "start_date": start,
                    "end_date": end,
                    "per_page": _PER_PAGE,
                    "page": page,
                },
            )
            games = data.get("data", [])
            if not games:
                break

            for raw in games:
                game = _upsert_game(db, raw)
                if game:
                    collected += 1

            db.commit()

            meta = data.get("meta", {})
            if page >= meta.get("total_pages", 1):
                break
            page += 1
            time.sleep(_RATE_LIMIT_DELAY)

    nba_q_games_collected_total.labels(season="recent").inc(collected)
    return collected
