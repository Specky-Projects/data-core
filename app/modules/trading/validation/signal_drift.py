"""Signal drift detection.

Compares the distribution of signals (BUY / SELL / HOLD) in a recent time window
against the full historical baseline to detect regime shifts, strategy degradation,
or data pipeline anomalies.

A "drift" is flagged when any signal type's share in the recent window deviates
from the historical baseline by more than ``DRIFT_THRESHOLD`` percentage points.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics.models import TradingAnalytics

# Drift is flagged when recent ratio deviates from historical by this many pp.
DRIFT_THRESHOLD: float = 0.20  # 20 percentage points


def compute_signal_drift(
    db: Session,
    symbol: str | None = None,
    timeframe: str | None = None,
    window_hours: int = 24,
) -> dict[str, Any]:
    """Compare recent signal distribution against historical baseline.

    Args:
        db: SQLAlchemy session.
        symbol: Optional symbol filter.
        timeframe: Optional timeframe filter.
        window_hours: Size of the recent window in hours (default 24).

    Returns:
        Dict with signal ratios (recent + historical), drift flag, and details.
    """
    now = datetime.now(tz=timezone.utc)
    window_start = now - timedelta(hours=window_hours)

    base_query = db.query(TradingAnalytics)
    if symbol:
        base_query = base_query.filter(TradingAnalytics.symbol == symbol)
    if timeframe:
        base_query = base_query.filter(TradingAnalytics.timeframe == timeframe)

    # Historical distribution (all time)
    historical_rows = (
        base_query
        .with_entities(TradingAnalytics.signal, func.count(TradingAnalytics.id))
        .group_by(TradingAnalytics.signal)
        .all()
    )

    # Recent distribution
    recent_rows = (
        base_query
        .filter(TradingAnalytics.calculated_at >= window_start)
        .with_entities(TradingAnalytics.signal, func.count(TradingAnalytics.id))
        .group_by(TradingAnalytics.signal)
        .all()
    )

    def _to_ratios(rows: list) -> dict[str, float]:
        counts = {row[0]: row[1] for row in rows if row[0]}
        total = sum(counts.values())
        if total == 0:
            return {}
        return {sig: round(cnt / total, 4) for sig, cnt in counts.items()}

    historical = _to_ratios(historical_rows)
    recent = _to_ratios(recent_rows)

    historical_total = sum(row[1] for row in historical_rows)
    recent_total = sum(row[1] for row in recent_rows)

    # Detect drift: any signal type deviating beyond threshold
    drift_signals: list[dict[str, Any]] = []
    all_signals = set(historical.keys()) | set(recent.keys())
    for sig in sorted(all_signals):
        hist_ratio = historical.get(sig, 0.0)
        rec_ratio = recent.get(sig, 0.0)
        deviation = abs(rec_ratio - hist_ratio)
        if deviation >= DRIFT_THRESHOLD:
            drift_signals.append({
                "signal": sig,
                "historical_ratio": hist_ratio,
                "recent_ratio": rec_ratio,
                "deviation_pp": round(deviation * 100, 2),
            })

    drift_detected = len(drift_signals) > 0

    return {
        "window_hours": window_hours,
        "recent_total": recent_total,
        "historical_total": historical_total,
        "recent_ratios": recent,
        "historical_ratios": historical,
        "drift_detected": drift_detected,
        "drift_threshold_pp": DRIFT_THRESHOLD * 100,
        "drifting_signals": drift_signals,
        "dominated_by_hold": recent.get("HOLD", 0.0) >= 0.90,
        "message": (
            f"Drift detected in {len(drift_signals)} signal type(s)"
            if drift_detected
            else "No significant drift detected"
        ),
    }
