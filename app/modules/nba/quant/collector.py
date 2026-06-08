"""
NBA game data collector.

Source priority:
1. Ball Don't Lie v2 (BALLDONTLIE_API_KEY set) — https://api.balldontlie.io/v1/
2. ESPN Scoreboard API (no key, works from VPS) — https://site.api.espn.com/

BDL v1 (https://www.balldontlie.io/api/v1/) was shut down — do not use.
stats.nba.com is blocked on datacenter IPs — do not use as primary source.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.modules.nba.quant.models import GameStatus, NbaGame

logger = logging.getLogger(__name__)

# ── BDL v2 ────────────────────────────────────────────────────────────────────
_API_KEY = os.environ.get("BALLDONTLIE_API_KEY", "")
_BASE_URL_V2 = "https://api.balldontlie.io/v1"
_BASE_URL_V1 = "https://www.balldontlie.io/api/v1"  # kept for reference only
_BASE_URL = _BASE_URL_V2 if _API_KEY else _BASE_URL_V1
_PER_PAGE = 100
_RATE_LIMIT_DELAY = 0.12 if _API_KEY else 1.1

# ── ESPN Scoreboard API ───────────────────────────────────────────────────────
_ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
_ESPN_DELAY = 0.3   # 200 req/min — stay conservative
_ESPN_CHUNK = 14    # days per request window

# NBA regular season windows per season-start year
# Format: (start_date, end_date) — inclusive, includes playoffs
_NBA_SEASON_WINDOWS: dict[int, tuple[str, str]] = {
    2019: ("2019-10-22", "2020-10-11"),
    2020: ("2020-12-22", "2021-07-20"),
    2021: ("2021-10-19", "2022-06-16"),
    2022: ("2022-10-18", "2023-06-12"),
    2023: ("2023-10-24", "2024-06-17"),
    2024: ("2024-10-22", "2025-06-22"),
}

# ── Full team name map (abbreviation → canonical full name) ───────────────────
_TEAM_NAMES: dict[str, str] = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "LA Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}


def _team_full_name(abbr: str) -> str:
    return _TEAM_NAMES.get(abbr.upper().strip(), abbr)


def _season_str(season: int) -> str:
    """Convert integer season start year to NBA season string. 2023 → '2023-24'."""
    return f"{season}-{str(season + 1)[-2:]}"


def _date_chunks(start: date, end: date, chunk_days: int = _ESPN_CHUNK) -> list[tuple[date, date]]:
    """Split a date range into chunks of at most chunk_days days."""
    chunks = []
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=chunk_days - 1), end)
        chunks.append((cur, chunk_end))
        cur = chunk_end + timedelta(days=1)
    return chunks


# ── Shared upsert ─────────────────────────────────────────────────────────────

def _upsert_game_record(  # noqa: PLR0913
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
) -> NbaGame:
    """Core upsert logic shared by all collectors."""
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


def _parse_game_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return None


# ── ESPN Scoreboard collector ─────────────────────────────────────────────────

def _parse_espn_event(event: dict, season: int) -> tuple[str, datetime, str, str, int | None, int | None, GameStatus] | None:  # noqa: E501
    """
    Parse one ESPN scoreboard event into (ext_id, date, home, away, home_score, away_score, status).
    Returns None if data is incomplete.
    """
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

    event_date_str = event.get("date", "")
    game_date = _parse_game_date(event_date_str)
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

    home_score = _score(home_team)
    away_score = _score(away_team)

    ext_id = f"espn_{event.get('id', '')}"
    return ext_id, game_date, home_name, away_name, home_score, away_score, status


def _fetch_espn_window(client: httpx.Client, start: date, end: date) -> list[dict]:
    """Fetch ESPN scoreboard events for a date window."""
    dates_param = f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"
    resp = client.get(
        _ESPN_BASE,
        params={"dates": dates_param, "limit": "1000"},
        timeout=20.0,
    )
    resp.raise_for_status()
    return resp.json().get("events", [])


def _fetch_season_espn(db: Session, season: int) -> int:
    """
    Fetch a complete NBA season from the ESPN Scoreboard API.

    Iterates the season window in 14-day chunks. No auth required.
    """
    from app.modules.nba.quant.metrics import nba_q_games_collected_total

    if season not in _NBA_SEASON_WINDOWS:
        raise ValueError(f"No season window defined for season {season}. "
                         f"Available: {sorted(_NBA_SEASON_WINDOWS)}")

    season_start_str, season_end_str = _NBA_SEASON_WINDOWS[season]
    season_start = date.fromisoformat(season_start_str)
    season_end = date.fromisoformat(season_end_str)
    # Don't fetch future dates
    season_end = min(season_end, date.today())

    chunks = _date_chunks(season_start, season_end)
    logger.info(
        "ESPN fetch_season start",
        extra={"season": season, "chunks": len(chunks), "start": season_start_str},
    )

    collected = 0
    batch_count = 0

    with httpx.Client() as client:
        for chunk_start, chunk_end in chunks:
            try:
                events = _fetch_espn_window(client, chunk_start, chunk_end)
            except Exception as exc:
                logger.warning(
                    "ESPN chunk fetch failed",
                    extra={"start": str(chunk_start), "end": str(chunk_end), "error": str(exc)},
                )
                time.sleep(1.0)
                continue

            for event in events:
                parsed = _parse_espn_event(event, season)
                if not parsed:
                    continue
                ext_id, game_date, home_name, away_name, home_score, away_score, status = parsed
                _upsert_game_record(
                    db,
                    external_id=ext_id,
                    season=season,
                    game_date=game_date,
                    home_name=home_name,
                    away_name=away_name,
                    home_score=home_score,
                    away_score=away_score,
                    status=status,
                )
                collected += 1
                batch_count += 1

            if batch_count >= 100:
                db.commit()
                batch_count = 0

            time.sleep(_ESPN_DELAY)

    db.commit()
    nba_q_games_collected_total.labels(season=str(season)).inc(collected)
    logger.info(
        "ESPN fetch_season done",
        extra={"season": season, "games": collected},
    )
    return collected


def _fetch_recent_espn(db: Session, days_back: int = 14) -> int:
    """Fetch recent games from ESPN to update live scores."""
    from app.modules.nba.quant.metrics import nba_q_games_collected_total

    today = date.today()
    start = today - timedelta(days=days_back)
    # Determine current season
    season = today.year if today.month >= 10 else today.year - 1

    logger.info("ESPN fetch_recent start", extra={"days_back": days_back, "start": str(start)})

    chunks = _date_chunks(start, today)
    collected = 0
    batch_count = 0

    with httpx.Client() as client:
        for chunk_start, chunk_end in chunks:
            try:
                events = _fetch_espn_window(client, chunk_start, chunk_end)
            except Exception as exc:
                logger.warning("ESPN recent chunk failed", extra={"error": str(exc)})
                continue

            for event in events:
                parsed = _parse_espn_event(event, season)
                if not parsed:
                    continue
                ext_id, game_date, home_name, away_name, home_score, away_score, status = parsed
                _upsert_game_record(
                    db,
                    external_id=ext_id,
                    season=season,
                    game_date=game_date,
                    home_name=home_name,
                    away_name=away_name,
                    home_score=home_score,
                    away_score=away_score,
                    status=status,
                )
                collected += 1
                batch_count += 1

            if batch_count >= 100:
                db.commit()
                batch_count = 0

            time.sleep(_ESPN_DELAY)

    db.commit()
    nba_q_games_collected_total.labels(season="recent").inc(collected)
    return collected


# ── Public API — auto-select source ──────────────────────────────────────────

def fetch_season(db: Session, season: int) -> int:
    """
    Fetch all regular-season games for *season*.
    Uses BDL v2 if BALLDONTLIE_API_KEY is set, otherwise ESPN Scoreboard API.
    """
    if _API_KEY:
        return _fetch_season_bdl(db, season)
    return _fetch_season_espn(db, season)


def fetch_recent(db: Session, days_back: int = 14) -> int:
    """
    Refresh recent game scores.
    Uses BDL v2 if BALLDONTLIE_API_KEY is set, otherwise ESPN Scoreboard API.
    """
    if _API_KEY:
        return _fetch_recent_bdl(db, days_back)
    return _fetch_recent_espn(db, days_back)


# ── BDL v2 implementations ────────────────────────────────────────────────────

def _make_headers() -> dict:
    if _API_KEY:
        return {"Authorization": _API_KEY}
    return {}


def _get_json_bdl(client: httpx.Client, url: str, params: dict) -> dict:
    resp = client.get(url, params=params, headers=_make_headers(), timeout=15.0)
    resp.raise_for_status()
    return resp.json()


def _upsert_game(db: Session, raw: dict) -> NbaGame | None:
    """Upsert a game from BDL v2 raw dict. Returns the game object or None."""
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

    return _upsert_game_record(
        db,
        external_id=external_id,
        season=season,
        game_date=game_date,
        home_name=home_name,
        away_name=away_name,
        home_score=home_score,
        away_score=away_score,
        status=status,
    )


def _fetch_season_bdl(db: Session, season: int) -> int:
    """Fetch all games for a given NBA season from Ball Don't Lie v2 API."""
    from app.modules.nba.quant.metrics import nba_q_games_collected_total

    logger.info("BDL v2 fetch_season start", extra={"season": season})
    collected = 0
    page = 1

    with httpx.Client() as client:
        while True:
            data = _get_json_bdl(
                client,
                f"{_BASE_URL_V2}/games",
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


def _fetch_recent_bdl(db: Session, days_back: int = 7) -> int:
    """Fetch recent games (last N days) from BDL v2 and update scores."""
    from app.modules.nba.quant.metrics import nba_q_games_collected_total

    collected = 0
    start = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with httpx.Client() as client:
        page = 1
        while True:
            data = _get_json_bdl(
                client,
                f"{_BASE_URL_V2}/games",
                {"start_date": start, "end_date": end, "per_page": _PER_PAGE, "page": page},
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


# ── NBA Stats API (disabled on VPS — datacenter IPs blocked) ─────────────────
# Kept for reference / local dev where stats.nba.com is accessible.

def _fetch_season_nba_stats(db: Session, season: int) -> int:  # noqa: ARG001
    raise NotImplementedError(
        "stats.nba.com is blocked on datacenter IPs. Use fetch_season_espn instead."
    )
