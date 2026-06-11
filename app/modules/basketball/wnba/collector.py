"""
WNBA game data collector — ESPN Scoreboard API (no auth required).

ESPN WNBA endpoint: https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard

WNBA season windows (regular season + playoffs):
  2022: 2022-05-06 → 2022-10-16
  2023: 2023-05-19 → 2023-10-22
  2024: 2024-05-14 → 2024-10-20
  2025: 2025-05-16 → 2025-10-19  (approximate)

Note: WNBA is in off-season from ~October to ~May.
      The collector will return 0 games during that period, which is expected.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.modules.basketball.shared.enums import GameStatus
from app.modules.basketball.wnba.models import WnbaGame

logger = logging.getLogger(__name__)

_ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"
_ESPN_DELAY = 0.3
_ESPN_CHUNK = 14

_WNBA_SEASON_WINDOWS: dict[int, tuple[str, str]] = {
    2022: ("2022-05-06", "2022-10-16"),
    2023: ("2023-05-19", "2023-10-22"),
    2024: ("2024-05-14", "2024-10-20"),
    2025: ("2025-05-16", "2025-10-19"),
}


def _date_chunks(start: date, end: date, chunk_days: int = _ESPN_CHUNK) -> list[tuple[date, date]]:
    chunks = []
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=chunk_days - 1), end)
        chunks.append((cur, chunk_end))
        cur = chunk_end + timedelta(days=1)
    return chunks


def _parse_game_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_espn_event(
    event: dict, season: int
) -> tuple[str, datetime, str, str, int | None, int | None, GameStatus] | None:
    comps = event.get("competitions", [])
    if not comps:
        return None
    comp = comps[0]

    competitors = comp.get("competitors", [])
    home_team = next((c for c in competitors if c.get("homeAway") == "home"), None)
    away_team = next((c for c in competitors if c.get("homeAway") == "away"), None)
    if not home_team or not away_team:
        return None

    home_name = home_team.get("team", {}).get("displayName", "")
    away_name = away_team.get("team", {}).get("displayName", "")
    if not home_name or not away_name:
        return None

    game_date = _parse_game_date(event.get("date", ""))
    if not game_date:
        return None

    status_name = comp.get("status", {}).get("type", {}).get("name", "")
    if status_name == "STATUS_FINAL":
        status = GameStatus.final
    elif status_name in ("STATUS_IN_PROGRESS", "STATUS_HALFTIME", "STATUS_END_PERIOD"):
        status = GameStatus.live
    else:
        status = GameStatus.scheduled

    def _score(competitor: dict) -> int | None:
        s = competitor.get("score")
        if s is None:
            return None
        try:
            return int(s)
        except (ValueError, TypeError):
            return None

    ext_id = f"espn_wnba_{event.get('id', '')}"
    return ext_id, game_date, home_name, away_name, _score(home_team), _score(away_team), status


def _upsert_game(
    db: Session,
    *,
    external_id: str,
    season: int,
    game_date: datetime,
    home_name: str,
    away_name: str,
    home_score: int | None,
    away_score: int | None,
    status: GameStatus,
) -> WnbaGame:
    existing = db.query(WnbaGame).filter(WnbaGame.external_id == external_id).first()
    if existing:
        existing.home_score = home_score
        existing.away_score = away_score
        existing.status = status
        existing.updated_at = datetime.now(timezone.utc)
        return existing

    existing_by_matchup = (
        db.query(WnbaGame)
        .filter(
            WnbaGame.home_team == home_name,
            WnbaGame.away_team == away_name,
            WnbaGame.game_date == game_date,
        )
        .first()
    )
    if existing_by_matchup:
        existing_by_matchup.external_id = external_id
        existing_by_matchup.home_score = home_score
        existing_by_matchup.away_score = away_score
        existing_by_matchup.status = status
        return existing_by_matchup

    game = WnbaGame(
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


def _fetch_espn_window(client: httpx.Client, start: date, end: date) -> list[dict]:
    dates_param = f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"
    resp = client.get(
        _ESPN_BASE,
        params={"dates": dates_param, "limit": "1000"},
        timeout=20.0,
    )
    resp.raise_for_status()
    return resp.json().get("events", [])


def fetch_season(db: Session, season: int) -> int:
    """Fetch all WNBA games for a season from ESPN. Returns games collected."""
    from app.modules.basketball.wnba.metrics import wnba_q_games_collected_total

    if season not in _WNBA_SEASON_WINDOWS:
        raise ValueError(
            f"No season window for WNBA season {season}. "
            f"Available: {sorted(_WNBA_SEASON_WINDOWS)}"
        )

    season_start = date.fromisoformat(_WNBA_SEASON_WINDOWS[season][0])
    season_end = min(date.fromisoformat(_WNBA_SEASON_WINDOWS[season][1]), date.today())

    chunks = _date_chunks(season_start, season_end)
    logger.info(
        "WNBA ESPN fetch_season start",
        extra={"season": season, "chunks": len(chunks)},
    )

    collected = 0
    batch_count = 0

    with httpx.Client() as client:
        for chunk_start, chunk_end in chunks:
            try:
                events = _fetch_espn_window(client, chunk_start, chunk_end)
            except Exception as exc:
                logger.warning("WNBA ESPN chunk failed", extra={"error": str(exc)})
                time.sleep(1.0)
                continue

            for event in events:
                parsed = _parse_espn_event(event, season)
                if not parsed:
                    continue
                ext_id, game_date, home_name, away_name, hs, as_, status = parsed
                _upsert_game(
                    db,
                    external_id=ext_id,
                    season=season,
                    game_date=game_date,
                    home_name=home_name,
                    away_name=away_name,
                    home_score=hs,
                    away_score=as_,
                    status=status,
                )
                collected += 1
                batch_count += 1

            if batch_count >= 100:
                db.commit()
                batch_count = 0

            time.sleep(_ESPN_DELAY)

    db.commit()
    wnba_q_games_collected_total.labels(season=str(season)).inc(collected)
    logger.info("WNBA ESPN fetch_season done", extra={"season": season, "games": collected})
    return collected


def fetch_recent(db: Session, days_back: int = 14) -> int:
    """Refresh recent WNBA game scores from ESPN."""
    from app.modules.basketball.wnba.metrics import wnba_q_games_collected_total

    today = date.today()
    start = today - timedelta(days=days_back)
    # WNBA season starts in May; determine by month
    season = today.year if today.month >= 5 else today.year - 1

    logger.info("WNBA ESPN fetch_recent start", extra={"days_back": days_back})

    chunks = _date_chunks(start, today)
    collected = 0
    batch_count = 0

    with httpx.Client() as client:
        for chunk_start, chunk_end in chunks:
            try:
                events = _fetch_espn_window(client, chunk_start, chunk_end)
            except Exception as exc:
                logger.warning("WNBA ESPN recent chunk failed", extra={"error": str(exc)})
                continue

            for event in events:
                parsed = _parse_espn_event(event, season)
                if not parsed:
                    continue
                ext_id, game_date, home_name, away_name, hs, as_, status = parsed
                _upsert_game(
                    db,
                    external_id=ext_id,
                    season=season,
                    game_date=game_date,
                    home_name=home_name,
                    away_name=away_name,
                    home_score=hs,
                    away_score=as_,
                    status=status,
                )
                collected += 1
                batch_count += 1

            if batch_count >= 100:
                db.commit()
                batch_count = 0

            time.sleep(_ESPN_DELAY)

    db.commit()
    wnba_q_games_collected_total.labels(season="recent").inc(collected)
    return collected
