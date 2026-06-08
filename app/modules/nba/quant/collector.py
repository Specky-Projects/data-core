"""
NBA game data collector.

Source priority:
1. Ball Don't Lie v2 (BALLDONTLIE_API_KEY set) — https://api.balldontlie.io/v1/
2. NBA Stats API (no key required)             — https://stats.nba.com/stats/

BDL v1 (https://www.balldontlie.io/api/v1/) was shut down — do not use.
"""
import logging
import os
import time
from datetime import datetime, timezone

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

# ── NBA Stats API ─────────────────────────────────────────────────────────────
_NBA_STATS_BASE = "https://stats.nba.com/stats"
_NBA_STATS_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Host": "stats.nba.com",
    "Origin": "https://www.nba.com",
    "Referer": "https://www.nba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}
_NBA_STATS_DELAY = 0.6  # ~100 req/min stay well under NBA throttle

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


# ── BDL helpers ───────────────────────────────────────────────────────────────

def _make_headers() -> dict:
    if _API_KEY:
        return {"Authorization": _API_KEY}
    return {}


def _get_json_bdl(client: httpx.Client, url: str, params: dict) -> dict:
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
    """Core upsert logic shared by BDL and NBA Stats collectors."""
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


# ── NBA Stats API collector ───────────────────────────────────────────────────

def _fetch_season_nba_stats(db: Session, season: int) -> int:
    """
    Fetch a full NBA regular season from stats.nba.com/stats/leaguegamelog.

    No API key required. Returns number of game records upserted.
    Each game appears as two rows (home team + away team); we pair them by
    GAME_ID and determine home/away from the MATCHUP column ("vs." = home).
    """
    from app.modules.nba.quant.metrics import nba_q_games_collected_total

    season_str = _season_str(season)
    logger.info(
        "NBA Stats fetch_season start",
        extra={"season": season, "season_str": season_str},
    )

    params = {
        "LeagueID": "00",
        "Season": season_str,
        "SeasonType": "Regular Season",
        "PlayerOrTeam": "T",
        "Direction": "ASC",
        "Sorter": "DATE",
    }

    with httpx.Client() as client:
        resp = client.get(
            f"{_NBA_STATS_BASE}/leaguegamelog",
            params=params,
            headers=_NBA_STATS_HEADERS,
            timeout=45.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()

    result_set = data["resultSets"][0]
    col = {h: i for i, h in enumerate(result_set["headers"])}
    rows = result_set["rowSet"]

    # Group by GAME_ID — each game has 2 rows
    games_by_id: dict[str, list[dict]] = {}
    for row in rows:
        gid = row[col["GAME_ID"]]
        games_by_id.setdefault(gid, []).append(row)

    collected = 0
    batch_count = 0

    for game_id, team_rows in games_by_id.items():
        if len(team_rows) != 2:
            continue

        r0, r1 = team_rows
        matchup0 = r0[col["MATCHUP"]]  # e.g. "LAL vs. BOS" or "LAL @ BOS"

        # "vs." means this team is home; "@" means this team is away
        if "vs." in matchup0:
            home_row, away_row = r0, r1
        else:
            away_row, home_row = r0, r1

        home_abbr = home_row[col["TEAM_ABBREVIATION"]]
        away_abbr = away_row[col["TEAM_ABBREVIATION"]]
        home_name = _team_full_name(home_abbr)
        away_name = _team_full_name(away_abbr)

        game_date_str = home_row[col["GAME_DATE"]]  # "2023-10-24"
        game_date = datetime.fromisoformat(game_date_str).replace(tzinfo=timezone.utc)

        home_pts = home_row[col["PTS"]]
        away_pts = away_row[col["PTS"]]
        home_score = int(home_pts) if home_pts is not None else None
        away_score = int(away_pts) if away_pts is not None else None

        # WL column: "W" or "L" → game is final; None → future/live
        wl = home_row[col["WL"]]
        status = GameStatus.final if wl in ("W", "L") else GameStatus.scheduled

        _upsert_game_record(
            db,
            external_id=f"nba_stats_{game_id}",
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

        if batch_count >= 50:
            db.commit()
            batch_count = 0

    db.commit()
    nba_q_games_collected_total.labels(season=str(season)).inc(collected)
    logger.info(
        "NBA Stats fetch_season done",
        extra={"season": season, "games": collected},
    )
    return collected


def _fetch_recent_nba_stats(db: Session, days_back: int = 14) -> int:
    """
    Refresh scores for recent games using stats.nba.com.
    Re-fetches the current season to pick up newly finalised scores.
    """
    from datetime import date

    current_month = date.today().month
    current_year = date.today().year
    # NBA season spans Oct–Jun; determine which season year we're in
    season = current_year if current_month >= 10 else current_year - 1
    return _fetch_season_nba_stats(db, season)


# ── Public API — auto-select source ──────────────────────────────────────────

def fetch_season(db: Session, season: int) -> int:
    """
    Fetch all regular-season games for *season*.
    Uses BDL v2 if BALLDONTLIE_API_KEY is set, otherwise NBA Stats API.
    """
    if _API_KEY:
        return _fetch_season_bdl(db, season)
    return _fetch_season_nba_stats(db, season)


def fetch_recent(db: Session, days_back: int = 7) -> int:
    """
    Refresh recent game scores.
    Uses BDL v2 if BALLDONTLIE_API_KEY is set, otherwise NBA Stats API.
    """
    if _API_KEY:
        return _fetch_recent_bdl(db, days_back)
    return _fetch_recent_nba_stats(db, days_back)


# ── BDL v2 implementations ────────────────────────────────────────────────────

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
    from datetime import timedelta

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
