"""Confidence calibration analysis.

Groups signal outcomes by confidence decile and computes accuracy per bin.
Answers the question: "Does higher confidence actually predict better outcomes?"

A well-calibrated strategy should show a positive correlation between
confidence decile and outcome_correct rate.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.modules.trading.validation.models import TradingSignalOutcome


def compute_calibration(
    db: Session,
    symbol: str | None = None,
    timeframe: str | None = None,
) -> dict[str, Any]:
    """Compute accuracy per confidence decile for evaluated signals.

    Args:
        db: SQLAlchemy session.
        symbol: Optional filter (e.g. "SOL/USDT").
        timeframe: Optional filter (e.g. "1h").

    Returns:
        Dict with keys:
          - ``deciles``: mapping "0-9" → {correct, total, accuracy}
          - ``overall_accuracy``: float 0.0-1.0
          - ``total_evaluated``: int
          - ``calibration_slope``: positive = higher confidence → higher accuracy
    """
    query = db.query(TradingSignalOutcome).filter(
        TradingSignalOutcome.outcome_correct.isnot(None),
    )
    if symbol:
        query = query.filter(TradingSignalOutcome.symbol == symbol)
    if timeframe:
        query = query.filter(TradingSignalOutcome.timeframe == timeframe)

    outcomes = query.all()

    if not outcomes:
        return {
            "deciles": {},
            "overall_accuracy": None,
            "total_evaluated": 0,
            "calibration_slope": None,
            "message": "No evaluated outcomes found.",
        }

    # Group into deciles 0-9, 10-19, …, 90-100
    bins: dict[str, dict[str, int]] = {}
    for low in range(0, 100, 10):
        high = low + 9 if low < 90 else 100
        bins[f"{low}-{high}"] = {"correct": 0, "total": 0}

    for outcome in outcomes:
        conf = outcome.confidence if outcome.confidence is not None else 0
        conf = max(0, min(100, conf))
        bucket_low = (conf // 10) * 10
        bucket_low = min(bucket_low, 90)
        high = bucket_low + 9 if bucket_low < 90 else 100
        key = f"{bucket_low}-{high}"
        bins[key]["total"] += 1
        if outcome.outcome_correct:
            bins[key]["correct"] += 1

    deciles: dict[str, Any] = {}
    x_vals: list[float] = []
    y_vals: list[float] = []

    for label, data in bins.items():
        if data["total"] > 0:
            accuracy = data["correct"] / data["total"]
            deciles[label] = {
                "correct": data["correct"],
                "total": data["total"],
                "accuracy": round(accuracy, 4),
            }
            midpoint = (int(label.split("-")[0]) + int(label.split("-")[1])) / 2
            x_vals.append(midpoint)
            y_vals.append(accuracy)

    # Simple calibration slope via least-squares (no external deps)
    slope: float | None = None
    if len(x_vals) >= 2:
        n = len(x_vals)
        mean_x = sum(x_vals) / n
        mean_y = sum(y_vals) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, y_vals))
        den = sum((x - mean_x) ** 2 for x in x_vals)
        slope = round(num / den, 6) if den != 0 else None

    total = len(outcomes)
    correct_total = sum(1 for o in outcomes if o.outcome_correct)
    overall = correct_total / total if total else None

    return {
        "deciles": deciles,
        "overall_accuracy": round(overall, 4) if overall is not None else None,
        "total_evaluated": total,
        "calibration_slope": slope,
        "well_calibrated": slope is not None and slope > 0,
    }
