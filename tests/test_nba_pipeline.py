"""
Unit tests for NBA Quant pipeline orchestration.
Mocks httpx and DB — no real API calls, no real database.
"""
from __future__ import annotations

import types
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.modules.nba.quant.collector import _parse_game_date, _upsert_game
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


# ── Collector env var ─────────────────────────────────────────────────────────

def test_collector_uses_v2_url_when_api_key_set():
    import importlib
    import os
    with patch.dict(os.environ, {"BALLDONTLIE_API_KEY": "test_key_123"}):
        import app.modules.nba.quant.collector as mod
        importlib.reload(mod)
        assert mod._API_KEY == "test_key_123"
        assert mod._BASE_URL == mod._BASE_URL_V2
        assert mod._RATE_LIMIT_DELAY < 1.0  # faster rate limit for v2
    # Restore
    importlib.reload(mod)


def test_collector_uses_v1_url_when_no_api_key():
    import importlib
    import os
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("BALLDONTLIE_API_KEY", None)
        import app.modules.nba.quant.collector as mod
        importlib.reload(mod)
        if not mod._API_KEY:
            assert mod._BASE_URL == mod._BASE_URL_V1
    importlib.reload(mod)


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
