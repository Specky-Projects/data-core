"""REST endpoints for trading signal validation.

Exposes outcome tracking, confidence calibration, and signal drift detection
so that external systems (Grafana, poupi-crypto, CI jobs) can query the
retrospective performance of BUY/SELL signals.

All endpoints are protected by the global API-key dependency registered in
``app.main``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from api.deps import db_session
from app.modules.trading.validation.confidence_calibration import compute_calibration
from app.modules.trading.validation.models import TradingSignalOutcome
from app.modules.trading.validation.outcome_tracker import SignalOutcomeTracker
from app.modules.trading.validation.signal_drift import compute_signal_drift

router = APIRouter(
    prefix="/api/v1/trading/validation",
    tags=["trading-validation"],
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _outcome_item(row: TradingSignalOutcome) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "analytics_id": str(row.analytics_id) if row.analytics_id else None,
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "signal": row.signal,
        "confidence": row.confidence,
        "regime": row.regime,
        "signal_price": _float(row.signal_price),
        "signal_at": row.signal_at.isoformat() if row.signal_at else None,
        "outcome_price": _float(row.outcome_price),
        "outcome_at": row.outcome_at.isoformat() if row.outcome_at else None,
        "candles_elapsed": row.candles_elapsed,
        "price_change_pct": _float(row.price_change_pct),
        "max_favorable_pct": _float(row.max_favorable_pct),
        "max_adverse_pct": _float(row.max_adverse_pct),
        "outcome_correct": row.outcome_correct,
        "evaluation_horizon_candles": row.evaluation_horizon_candles,
        "evaluated_at": row.evaluated_at.isoformat() if row.evaluated_at else None,
    }


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/signal-outcomes")
def list_signal_outcomes(
    db: Session = Depends(db_session),
    symbol: str | None = Query(default=None, description="Filter by symbol, e.g. SOL/USDT"),
    timeframe: str | None = Query(default=None, description="Filter by timeframe, e.g. 1h"),
    signal: str | None = Query(default=None, description="Filter by signal type: BUY or SELL"),
    outcome_correct: bool | None = Query(default=None, description="Filter by outcome correctness"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    """List evaluated signal outcomes, most recent first.

    Returns a paginated list of retrospective BUY/SELL signal evaluations with
    price change, MFE, MAE, and correctness label.
    """
    query = db.query(TradingSignalOutcome).order_by(desc(TradingSignalOutcome.signal_at))

    if symbol:
        query = query.filter(TradingSignalOutcome.symbol == symbol)
    if timeframe:
        query = query.filter(TradingSignalOutcome.timeframe == timeframe)
    if signal:
        query = query.filter(TradingSignalOutcome.signal == signal.upper())
    if outcome_correct is not None:
        query = query.filter(TradingSignalOutcome.outcome_correct == outcome_correct)

    rows = query.limit(limit).all()
    return {
        "count": len(rows),
        "limit": limit,
        "items": [_outcome_item(r) for r in rows],
    }


@router.get("/calibration")
def get_calibration(
    db: Session = Depends(db_session),
    symbol: str | None = Query(default=None, description="Optional symbol filter"),
    timeframe: str | None = Query(default=None, description="Optional timeframe filter"),
) -> dict[str, Any]:
    """Confidence calibration analysis by decile.

    Groups evaluated outcomes by confidence decile (0–9, 10–19, … 90–100) and
    returns accuracy per bin.  A positive ``calibration_slope`` indicates that
    higher confidence scores correlate with better outcomes (well-calibrated).
    """
    return compute_calibration(db, symbol=symbol, timeframe=timeframe)


@router.get("/signal-drift")
def get_signal_drift(
    db: Session = Depends(db_session),
    symbol: str | None = Query(default=None, description="Optional symbol filter"),
    timeframe: str | None = Query(default=None, description="Optional timeframe filter"),
    window_hours: int = Query(
        default=24,
        ge=1,
        le=720,
        description="Size of the recent window in hours to compare against historical baseline",
    ),
) -> dict[str, Any]:
    """Signal distribution drift detection.

    Compares the BUY/SELL/HOLD distribution in the recent window against the
    full historical baseline.  A drift is flagged when any signal type's share
    deviates by more than 20 percentage points.
    """
    return compute_signal_drift(
        db,
        symbol=symbol,
        timeframe=timeframe,
        window_hours=window_hours,
    )


@router.post("/run-outcome-tracker")
def run_outcome_tracker(
    db: Session = Depends(db_session),
    limit: int = Query(
        default=200,
        ge=1,
        le=2000,
        description="Maximum number of pending signals to evaluate in this run",
    ),
) -> dict[str, Any]:
    """Manually trigger the signal outcome tracker.

    Evaluates up to ``limit`` pending BUY/SELL signals that have not yet been
    assessed.  Returns a summary with evaluated / skipped / error counts.

    This endpoint mirrors the scheduler job that runs automatically every hour.
    Useful for backfilling outcomes after a deployment or data pipeline recovery.
    """
    tracker = SignalOutcomeTracker(db)
    result = tracker.run(limit=limit)
    return result
