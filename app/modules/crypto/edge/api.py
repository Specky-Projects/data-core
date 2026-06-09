"""REST endpoints for crypto signal edge validation."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from api.deps import db_session
from app.modules.crypto.edge.calculator import (
    HORIZONS_HOURS,
    EdgeOutcomeTracker,
    build_edge_report,
    build_phase7_report,
)
from app.modules.crypto.edge.forward import ForwardShadowTracker, build_forward_validation_report
from app.modules.crypto.edge.models import SignalEdgeOutcome

router = APIRouter(prefix="/api/v1/crypto/edge", tags=["crypto-edge"])


def _float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _outcome_item(row: SignalEdgeOutcome) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "analytics_id": str(row.analytics_id) if row.analytics_id else None,
        "horizon_hours": row.horizon_hours,
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "signal": row.signal,
        "confidence": row.confidence,
        "regime": row.regime,
        "signal_at": row.signal_at.isoformat() if row.signal_at else None,
        "signal_price": _float(row.signal_price),
        "outcome_at": row.outcome_at.isoformat() if row.outcome_at else None,
        "outcome_price": _float(row.outcome_price),
        "candles_elapsed": row.candles_elapsed,
        "price_change_pct": _float(row.price_change_pct),
        "mfe_pct": _float(row.mfe_pct),
        "mae_pct": _float(row.mae_pct),
        "outcome_correct": row.outcome_correct,
        "computed_at": row.computed_at.isoformat() if row.computed_at else None,
    }


# ---------------------------------------------------------------------------
# Phase 6 endpoints (preserved)
# ---------------------------------------------------------------------------


@router.get("")
def get_edge_report(
    db: Session = Depends(db_session),  # noqa: B008
    horizon_hours: int | None = Query(
        default=None,
        description="Filter to a specific horizon: 24 | 72 | 168 | 336.",
    ),
    symbol: str | None = Query(default=None, description="Filter by symbol, e.g. BTC/USDT"),
    timeframe: str | None = Query(default=None, description="Filter by timeframe, e.g. 1h"),
) -> dict[str, Any]:
    """Full edge validation report (Phase 6 format)."""
    if horizon_hours is not None and horizon_hours not in HORIZONS_HOURS:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail=f"horizon_hours must be one of {HORIZONS_HOURS}",
        )
    return build_edge_report(db, horizon_hours=horizon_hours, symbol=symbol, timeframe=timeframe)


@router.post("/compute")
def compute_edge_outcomes(
    db: Session = Depends(db_session),  # noqa: B008
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    """Trigger multi-horizon edge outcome computation (idempotent)."""
    tracker = EdgeOutcomeTracker(db)
    return tracker.run(limit=limit)


@router.get("/outcomes")
def list_edge_outcomes(
    db: Session = Depends(db_session),  # noqa: B008
    symbol: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    horizon_hours: int | None = Query(default=None),
    outcome_correct: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    """List raw edge outcome rows, most recent signal first."""
    query = db.query(SignalEdgeOutcome).order_by(desc(SignalEdgeOutcome.signal_at))
    if symbol:
        query = query.filter(SignalEdgeOutcome.symbol == symbol)
    if timeframe:
        query = query.filter(SignalEdgeOutcome.timeframe == timeframe)
    if horizon_hours is not None:
        query = query.filter(SignalEdgeOutcome.horizon_hours == horizon_hours)
    if outcome_correct is not None:
        query = query.filter(SignalEdgeOutcome.outcome_correct == outcome_correct)
    rows = query.limit(limit).all()
    return {
        "count": len(rows),
        "items": [_outcome_item(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# Phase 7 endpoint
# ---------------------------------------------------------------------------


@router.get("/edge-report")
def get_edge_report_v7(
    db: Session = Depends(db_session),  # noqa: B008
    symbol: str | None = Query(default=None, description="Filter by symbol, e.g. BTC/USDT"),
    timeframe: str | None = Query(default=None, description="Filter by timeframe, e.g. 1h"),
) -> dict[str, Any]:
    """Phase 7 expanded edge report.

    Returns:
    - regime_intelligence: per-regime metrics across all horizons (24h/72h/168h/336h)
    - confidence_intelligence: per-bucket metrics across all horizons
    - shadow_strategy: regime=UNKNOWN AND confidence>=75 (observation-only)
    - strategy_comparison: current strategy vs shadow at each horizon
    - go_no_go_by_segment: verdict per regime, bucket, and shadow
    - best_regime, best_bucket, overall_verdict
    - outcomes: all raw outcome rows with shadow flag
    """
    return build_phase7_report(db, symbol=symbol, timeframe=timeframe)


# ---------------------------------------------------------------------------
# Phase 8 endpoints
# ---------------------------------------------------------------------------


@router.get("/forward-validation")
def get_forward_validation(
    db: Session = Depends(db_session),  # noqa: B008
    run_tracker: bool = Query(
        default=True,
        description="Run ForwardShadowTracker before generating report (idempotent).",
    ),
) -> dict[str, Any]:
    """Phase 8 forward shadow validation report.

    Tracks BUY signals with regime=UNKNOWN AND confidence 75-84.
    Observation only — no trades, no strategy changes.

    Returns per-horizon metrics (24h/72h/168h):
    N, WR, avg_return, PF, Sharpe, alert_flags, GO/NO-GO.

    Alert flags:
    - WR_BELOW_55: win rate fell below 55%
    - PF_BELOW_1.5: profit factor fell below 1.5
    - AVG_RETURN_NEGATIVE: average return is negative
    """
    return build_forward_validation_report(db, run_tracker=run_tracker)


@router.post("/compute-forward")
def compute_forward_shadow(
    db: Session = Depends(db_session),  # noqa: B008
) -> dict[str, Any]:
    """Trigger forward shadow tracker: capture new signals + compute pending outcomes.

    Idempotent — safe to call repeatedly.
    """
    tracker = ForwardShadowTracker()
    return tracker.run(db)


# ---------------------------------------------------------------------------
# Phase 9 endpoints
# ---------------------------------------------------------------------------


@router.get("/readiness")
def get_readiness_report(
    db: Session = Depends(db_session),  # noqa: B008
) -> dict[str, Any]:
    """Phase 9 Forward Validation Readiness Panel.

    Provides per-horizon (24h / 72h / 168h):
    - Readiness score: BOOTSTRAP / EARLY_SAMPLE / MODERATE_SAMPLE / STATISTICALLY_RELEVANT
    - Sample gates: n >= 10 / 30 / 100
    - 95 % confidence intervals: win rate (Wilson), avg_return (normal), PF (delta)
    - Edge status: INSUFFICIENT_DATA / NO_EDGE / POSSIBLE_EDGE / EDGE_DETECTED

    Plus overall_verdict (GO / WATCH / NO_GO / INSUFFICIENT_DATA).
    """
    from app.modules.crypto.edge.readiness import build_readiness_report

    return build_readiness_report(db)


# ---------------------------------------------------------------------------
# Phase 10 endpoints
# ---------------------------------------------------------------------------


@router.post("/daily-summary")
def send_daily_summary_endpoint(
    db: Session = Depends(db_session),  # noqa: B008
    force: bool = Query(
        default=False,
        description="Force send even if already sent today.",
    ),
) -> dict[str, Any]:
    """Send Phase 10 daily Telegram summary (deduped — max once per day)."""
    from app.modules.crypto.edge.telegram_ops import send_daily_summary

    return send_daily_summary(db, force=force)


@router.post("/check-edge-alerts")
def check_edge_alerts_endpoint(
    db: Session = Depends(db_session),  # noqa: B008
) -> dict[str, Any]:
    """Phase 10 — check and fire Telegram edge alerts.

    Fires:
    - Gate crossings: n >= 10 / 30 / 100 (once per gate per horizon)
    - Edge status changes (INSUFFICIENT_DATA → NO_EDGE → POSSIBLE_EDGE → EDGE_DETECTED)
    - WR < 50% or PF < 1.5 after n >= 10 (fires on degradation)
    """
    from app.modules.crypto.edge.telegram_ops import check_and_send_edge_alerts

    return check_and_send_edge_alerts(db)


@router.post("/weekly-report")
def send_weekly_report_endpoint(
    db: Session = Depends(db_session),  # noqa: B008
    force: bool = Query(
        default=False,
        description="Force send even if already sent this ISO week.",
    ),
) -> dict[str, Any]:
    """Send Phase 10 weekly Telegram report (deduped — max once per ISO week).

    Includes: per-horizon metrics, regime breakdown, confidence bucket breakdown,
    best/worst segment, overall verdict.
    """
    from app.modules.crypto.edge.telegram_ops import send_weekly_report

    return send_weekly_report(db, force=force)


@router.post("/run-quant-ops")
def run_quant_ops_endpoint(
    db: Session = Depends(db_session),  # noqa: B008
    force: bool = Query(
        default=False,
        description="Force all sends (ignore dedup).",
    ),
) -> dict[str, Any]:
    """Phase 10 — run all Telegram quant ops in one call.

    Executes: daily summary + edge alerts + weekly report (Monday only, unless force).
    Observation only — no trades, no orders, no strategy changes.
    """
    from app.modules.crypto.edge.telegram_ops import run_all_ops

    return run_all_ops(db, force=force)
