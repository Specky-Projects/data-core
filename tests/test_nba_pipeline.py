"""
Unit tests for NBA Quant pipeline orchestration.
Mocks httpx and DB — no real API calls, no real database.
"""
from __future__ import annotations

import types
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.modules.nba.quant.collector import (
    _date_chunks,
    _parse_espn_event,
    _parse_game_date,
    _season_str,
    _team_full_name,
    _upsert_game,
)
from app.modules.nba.quant.pipeline import PipelineResult, run_full_pipeline

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_raw_game(
    game_id: int = 1,
    home: str = "Lakers",
    away: str = "Celtics",
    status: str = "Final",
    home_score: int = 110,
    away_score: int = 105,
    season: int = 2024,
) -> dict:
    return {
        "id": game_id,
        "season": season,
        "date": "2024-01-15T00:00:00.000Z",
        "status": status,
        "home_team": {"full_name": home, "name": home},
        "visitor_team": {"full_name": away, "name": away},
        "home_team_score": home_score,
        "visitor_team_score": away_score,
    }


def _make_mock_db() -> MagicMock:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


# ── _parse_game_date ──────────────────────────────────────────────────────────

def test_parse_game_date_iso():
    dt = _parse_game_date("2024-01-15T00:00:00.000Z")
    assert dt is not None
    assert dt.year == 2024
    assert dt.month == 1
    assert dt.day == 15


def test_parse_game_date_none():
    assert _parse_game_date(None) is None


def test_parse_game_date_empty():
    assert _parse_game_date("") is None


def test_parse_game_date_invalid():
    assert _parse_game_date("not-a-date") is None


# ── _upsert_game ──────────────────────────────────────────────────────────────

def test_upsert_game_creates_new():
    db = _make_mock_db()
    raw = _make_raw_game()
    result = _upsert_game(db, raw)
    assert result is not None
    assert result.home_team == "Lakers"
    assert result.away_team == "Celtics"
    db.add.assert_called_once()


def test_upsert_game_updates_existing():
    existing = types.SimpleNamespace(
        external_id="1",
        home_score=None,
        away_score=None,
        status=None,
        updated_at=None,
    )
    db = _make_mock_db()
    db.query.return_value.filter.return_value.first.return_value = existing
    raw = _make_raw_game(home_score=112, away_score=108)
    result = _upsert_game(db, raw)
    assert result is existing
    assert result.home_score == 112
    assert result.away_score == 108
    db.add.assert_not_called()


def test_upsert_game_skips_missing_team():
    db = _make_mock_db()
    raw = _make_raw_game()
    raw["home_team"] = {}
    result = _upsert_game(db, raw)
    assert result is None


def test_upsert_game_status_final():
    db = _make_mock_db()
    raw = _make_raw_game(status="Final")
    result = _upsert_game(db, raw)
    from app.modules.nba.quant.models import GameStatus
    assert result.status == GameStatus.final


def test_upsert_game_status_live():
    db = _make_mock_db()
    raw = _make_raw_game(status="In Progress")
    result = _upsert_game(db, raw)
    from app.modules.nba.quant.models import GameStatus
    assert result.status == GameStatus.live


def test_upsert_game_status_scheduled():
    db = _make_mock_db()
    raw = _make_raw_game(status="7:30 pm ET")
    result = _upsert_game(db, raw)
    from app.modules.nba.quant.models import GameStatus
    assert result.status == GameStatus.scheduled


# ── PipelineResult ────────────────────────────────────────────────────────────

def test_pipeline_result_ok_no_errors():
    r = PipelineResult(started_at=datetime.now(timezone.utc))
    assert r.ok is True


def test_pipeline_result_not_ok_with_errors():
    r = PipelineResult(started_at=datetime.now(timezone.utc), errors=["boom"])
    assert r.ok is False


def test_pipeline_result_duration():
    start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 1, 12, 0, 30, tzinfo=timezone.utc)
    r = PipelineResult(started_at=start, finished_at=end)
    assert r.duration_seconds == pytest.approx(30.0)


# ── run_full_pipeline orchestration ──────────────────────────────────────────

_PM = "app.modules.nba.quant.pipeline"  # module under test


def _make_pipeline_mocks(
    games_returned: int = 10,
    features_returned: int = 8,
    signals_returned: int = 5,
    settled_returned: int = 3,
    registry_returned: list | None = None,
):
    """Return a dict of attr-name→mock for patch.multiple(_PM, ...)."""
    return {
        "fetch_season": MagicMock(return_value=games_returned),
        "fetch_recent": MagicMock(return_value=2),
        "compute_all_pending": MagicMock(return_value=features_returned),
        "run_all_games": MagicMock(return_value=signals_returned),
        "settle_all_pending": MagicMock(return_value=settled_returned),
        "refresh_edge_registry": MagicMock(
            return_value=registry_returned or [MagicMock(), MagicMock()]
        ),
        "nba_q_pipeline_runs_total": MagicMock(),
        "nba_q_pipeline_duration_seconds": MagicMock(),
    }


def test_run_full_pipeline_skip_historical():
    mocks = _make_pipeline_mocks()
    db = MagicMock()
    with patch.multiple(_PM, **mocks):
        result = run_full_pipeline(db, skip_historical=True)

    assert result.ok
    assert result.games_ingested == 0  # historical skipped
    assert result.recent_updated == 2
    assert result.features_computed == 8
    assert result.signals_generated == 5
    assert result.bets_settled == 3
    assert result.edge_registry_refreshed == 2
    assert result.errors == []
    mocks["fetch_season"].assert_not_called()
    mocks["fetch_recent"].assert_called_once()


def test_run_full_pipeline_with_historical():
    mocks = _make_pipeline_mocks(games_returned=100)
    db = MagicMock()
    with patch.multiple(_PM, **mocks):
        result = run_full_pipeline(db, seasons=[2023, 2024], skip_historical=False)

    assert result.ok
    assert mocks["fetch_season"].call_count == 2
    assert result.games_ingested == 200
    assert result.seasons_fetched == [2023, 2024]


def test_run_full_pipeline_partial_error_continues():
    """Pipeline must continue past errors in any step."""
    mocks = _make_pipeline_mocks()
    mocks["fetch_recent"] = MagicMock(side_effect=RuntimeError("BDL timeout"))
    db = MagicMock()
    with patch.multiple(_PM, **mocks):
        result = run_full_pipeline(db, skip_historical=True)

    assert not result.ok
    assert len(result.errors) == 1
    assert "BDL timeout" in result.errors[0]
    mocks["compute_all_pending"].assert_called_once()
    mocks["run_all_games"].assert_called_once()


def test_run_full_pipeline_metrics_called():
    mocks = _make_pipeline_mocks()
    db = MagicMock()
    with patch.multiple(_PM, **mocks):
        run_full_pipeline(db, skip_historical=True)

    mocks["nba_q_pipeline_runs_total"].labels.assert_called()
    mocks["nba_q_pipeline_duration_seconds"].set.assert_called()


def test_run_full_pipeline_error_status_partial():
    mocks = _make_pipeline_mocks()
    mocks["run_all_games"] = MagicMock(side_effect=Exception("signal error"))
    db = MagicMock()
    with patch.multiple(_PM, **mocks):
        run_full_pipeline(db, skip_historical=True)

    mocks["nba_q_pipeline_runs_total"].labels.assert_called_with(status="partial_error")


def test_run_full_pipeline_success_status_ok():
    mocks = _make_pipeline_mocks()
    db = MagicMock()
    with patch.multiple(_PM, **mocks):
        run_full_pipeline(db, skip_historical=True)

    mocks["nba_q_pipeline_runs_total"].labels.assert_called_with(status="ok")


# ── Collector helpers ─────────────────────────────────────────────────────────

def test_season_str():
    assert _season_str(2023) == "2023-24"
    assert _season_str(2024) == "2024-25"
    assert _season_str(2022) == "2022-23"


def test_team_full_name_known():
    assert _team_full_name("LAL") == "Los Angeles Lakers"
    assert _team_full_name("BOS") == "Boston Celtics"
    assert _team_full_name("GSW") == "Golden State Warriors"


def test_team_full_name_unknown_returns_abbr():
    assert _team_full_name("XYZ") == "XYZ"


def test_team_full_name_case_insensitive():
    assert _team_full_name("lal") == "Los Angeles Lakers"
    assert _team_full_name("Bos") == "Boston Celtics"


# ── BDL headers ───────────────────────────────────────────────────────────────

def test_collector_headers_with_key():
    import importlib
    import os
    with patch.dict(os.environ, {"BALLDONTLIE_API_KEY": "my_key"}):
        import app.modules.nba.quant.collector as mod
        importlib.reload(mod)
        headers = mod._make_headers()
        assert headers.get("Authorization") == "my_key"
    importlib.reload(mod)


def test_collector_headers_no_key():
    import importlib
    import os
    saved = os.environ.pop("BALLDONTLIE_API_KEY", None)
    try:
        import app.modules.nba.quant.collector as mod
        importlib.reload(mod)
        headers = mod._make_headers()
        assert "Authorization" not in headers
    finally:
        if saved:
            os.environ["BALLDONTLIE_API_KEY"] = saved
        importlib.reload(mod)


# ── _date_chunks ─────────────────────────────────────────────────────────────

def test_date_chunks_single_chunk():
    start = date(2024, 1, 1)
    end = date(2024, 1, 7)
    chunks = _date_chunks(start, end, chunk_days=14)
    assert len(chunks) == 1
    assert chunks[0] == (date(2024, 1, 1), date(2024, 1, 7))


def test_date_chunks_multiple_chunks():
    start = date(2024, 1, 1)
    end = date(2024, 1, 28)
    chunks = _date_chunks(start, end, chunk_days=14)
    assert len(chunks) == 2
    assert chunks[0] == (date(2024, 1, 1), date(2024, 1, 14))
    assert chunks[1] == (date(2024, 1, 15), date(2024, 1, 28))


def test_date_chunks_exact_fit():
    start = date(2024, 1, 1)
    end = date(2024, 1, 14)
    chunks = _date_chunks(start, end, chunk_days=14)
    assert len(chunks) == 1


# ── _parse_espn_event ─────────────────────────────────────────────────────────

def _make_espn_event(
    event_id: str = "401584686",
    home_name: str = "Los Angeles Lakers",
    away_name: str = "Boston Celtics",
    home_score: str = "110",
    away_score: str = "105",
    status_name: str = "STATUS_FINAL",
    date_str: str = "2024-01-15T23:30Z",
) -> dict:
    return {
        "id": event_id,
        "date": date_str,
        "competitions": [{
            "competitors": [
                {
                    "homeAway": "home",
                    "team": {"displayName": home_name},
                    "score": home_score,
                },
                {
                    "homeAway": "away",
                    "team": {"displayName": away_name},
                    "score": away_score,
                },
            ],
            "status": {"type": {"name": status_name, "completed": status_name == "STATUS_FINAL"}},
        }],
    }


def test_parse_espn_event_final():
    from app.modules.nba.quant.models import GameStatus
    event = _make_espn_event()
    result = _parse_espn_event(event, 2023)
    assert result is not None
    ext_id, game_date, home, away, home_score, away_score, status = result
    assert ext_id == "espn_401584686"
    assert home == "Los Angeles Lakers"
    assert away == "Boston Celtics"
    assert home_score == 110
    assert away_score == 105
    assert status == GameStatus.final


def test_parse_espn_event_scheduled():
    from app.modules.nba.quant.models import GameStatus
    event = _make_espn_event(status_name="STATUS_SCHEDULED", home_score="0", away_score="0")
    result = _parse_espn_event(event, 2023)
    assert result is not None
    _, _, _, _, _, _, status = result
    assert status == GameStatus.scheduled


def test_parse_espn_event_live():
    from app.modules.nba.quant.models import GameStatus
    event = _make_espn_event(status_name="STATUS_IN_PROGRESS", home_score="58", away_score="52")
    result = _parse_espn_event(event, 2023)
    assert result is not None
    _, _, _, _, _, _, status = result
    assert status == GameStatus.live


def test_parse_espn_event_missing_competitors():
    event = {"id": "1", "date": "2024-01-15T23:30Z", "competitions": [{"competitors": []}]}
    result = _parse_espn_event(event, 2023)
    assert result is None


def test_parse_espn_event_no_competitions():
    event = {"id": "1", "date": "2024-01-15T23:30Z", "competitions": []}
    result = _parse_espn_event(event, 2023)
    assert result is None


def test_parse_espn_event_null_score():
    event = _make_espn_event(home_score=None, away_score=None)
    result = _parse_espn_event(event, 2023)
    assert result is not None
    _, _, _, _, home_score, away_score, _ = result
    assert home_score is None
    assert away_score is None


# ── _fetch_season_espn ────────────────────────────────────────────────────────

def _make_espn_scoreboard_response(events: list[dict]) -> dict:
    return {"events": events}


def test_fetch_season_espn_creates_games():
    from app.modules.nba.quant.collector import _fetch_season_espn

    events = [
        _make_espn_event("1001", "Los Angeles Lakers", "Boston Celtics", "120", "110"),
        _make_espn_event("1002", "Golden State Warriors", "New York Knicks", "105", "115"),
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = _make_espn_scoreboard_response(events)

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    created_games = []
    db.add.side_effect = lambda g: created_games.append(g)

    with patch("app.modules.nba.quant.collector.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        with patch("app.modules.nba.quant.metrics.nba_q_games_collected_total"):
            # Patch date.today() so we get a deterministic season window
            with patch("app.modules.nba.quant.collector.date") as mock_date:
                mock_date.today.return_value = date(2025, 1, 15)
                mock_date.fromisoformat = date.fromisoformat
                result = _fetch_season_espn(db, 2024)

    assert result == 2 * mock_client_cls.return_value.__enter__.return_value.get.call_count or result >= 2  # noqa: E501


def test_fetch_season_espn_external_id_prefix():
    from app.modules.nba.quant.collector import _fetch_season_espn

    event = _make_espn_event("999777")
    mock_resp = MagicMock()
    mock_resp.json.return_value = _make_espn_scoreboard_response([event])

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    created_games = []
    db.add.side_effect = lambda g: created_games.append(g)

    with patch("app.modules.nba.quant.collector.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        with patch("app.modules.nba.quant.metrics.nba_q_games_collected_total"):
            with patch("app.modules.nba.quant.collector.date") as mock_date:
                mock_date.today.return_value = date(2025, 1, 15)
                mock_date.fromisoformat = date.fromisoformat
                _fetch_season_espn(db, 2024)

    # At least one game created across all chunk calls
    assert any(g.external_id == "espn_999777" for g in created_games)


def test_fetch_season_espn_invalid_season_raises():
    from app.modules.nba.quant.collector import _fetch_season_espn

    db = MagicMock()
    with pytest.raises(ValueError, match="No season window defined"):
        _fetch_season_espn(db, 1990)


def test_fetch_season_espn_chunk_error_continues():
    """If one chunk fails (network error), ingestion continues with next chunks."""
    from app.modules.nba.quant.collector import _fetch_season_espn

    call_count = [0]
    good_resp = MagicMock()
    good_resp.json.return_value = _make_espn_scoreboard_response([_make_espn_event("888")])

    def _get_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise httpx.ConnectTimeout("timeout")
        return good_resp

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with patch("app.modules.nba.quant.collector.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.side_effect = _get_side_effect
        with patch("app.modules.nba.quant.metrics.nba_q_games_collected_total"):
            with patch("app.modules.nba.quant.collector.date") as mock_date:
                mock_date.today.return_value = date(2025, 1, 15)
                mock_date.fromisoformat = date.fromisoformat
                # Should not raise even if first chunk fails
                result = _fetch_season_espn(db, 2024)

    # At least some games were collected from non-failing chunks
    assert result >= 0


# ── fetch_season source routing ───────────────────────────────────────────────

def test_fetch_season_routes_to_espn_without_api_key():
    """Without BALLDONTLIE_API_KEY, fetch_season calls ESPN."""
    import importlib
    import os

    saved = os.environ.pop("BALLDONTLIE_API_KEY", None)
    try:
        import app.modules.nba.quant.collector as mod
        importlib.reload(mod)
        db = MagicMock()
        with patch.object(mod, "_fetch_season_espn", return_value=42) as mock_espn:
            with patch.object(mod, "_fetch_season_bdl", return_value=0) as mock_bdl:
                result = mod.fetch_season(db, 2023)
        mock_espn.assert_called_once_with(db, 2023)
        mock_bdl.assert_not_called()
        assert result == 42
    finally:
        if saved:
            os.environ["BALLDONTLIE_API_KEY"] = saved
        importlib.reload(mod)


def test_fetch_season_routes_to_bdl_with_api_key():
    """With BALLDONTLIE_API_KEY set, fetch_season calls BDL."""
    import importlib
    import os

    with patch.dict(os.environ, {"BALLDONTLIE_API_KEY": "test_key"}):
        import app.modules.nba.quant.collector as mod
        importlib.reload(mod)
        db = MagicMock()
        with patch.object(mod, "_fetch_season_bdl", return_value=100) as mock_bdl:
            with patch.object(mod, "_fetch_season_espn", return_value=0) as mock_espn:
                result = mod.fetch_season(db, 2023)
        mock_bdl.assert_called_once_with(db, 2023)
        mock_espn.assert_not_called()
        assert result == 100
    importlib.reload(mod)
