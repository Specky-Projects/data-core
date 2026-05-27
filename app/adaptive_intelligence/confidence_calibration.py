"""ConfidenceCalibrationEngine — bucket-by-bucket calibration analysis.

Buckets: 0-20, 21-40, 41-60, 61-80, 81-100 (by signal confidence score).

Advisory-only: reads TradingSignalOutcome rows, never writes.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.adaptive_intelligence.dto import (
    CalibrationBucket,
    ConfidenceCalibrationResult,
)
from app.modules.trading.validation.models import TradingSignalOutcome

logger = logging.getLogger(__name__)

# Confidence bucket definitions: (label, lower, upper)
_BUCKETS: list[tuple[str, int, int]] = [
    ("0-20",   0,  20),
    ("21-40", 21,  40),
    ("41-60", 41,  60),
    ("61-80", 61,  80),
    ("81-100", 81, 100),
]

# A slice is "well-calibrated" if realized win_rate ≥ this threshold
_CALIBRATED_WIN_RATE_THRESHOLD = 0.55

# Calibration gap thresholds for over/underconfidence flags
_OVERCONFIDENCE_GAP = -0.10   # realized << predicted  (negative gap)
_UNDERCONFIDENCE_GAP = 0.10   # realized >> predicted  (positive gap)


class _BucketAcc:
    """Raw accumulator for one confidence bucket."""

    __slots__ = ("confidence_sum", "wins", "losses", "returns")

    def __init__(self) -> None:
        self.confidence_sum: float = 0.0
        self.wins: int = 0
        self.losses: int = 0
        self.returns: list[float] = []

    def add(self, confidence: int, correct: bool, price_change_pct: float) -> None:
        self.confidence_sum += confidence
        self.returns.append(price_change_pct)
        if correct:
            self.wins += 1
        else:
            self.losses += 1

    @property
    def sample_size(self) -> int:
        return self.wins + self.losses

    @property
    def predicted_confidence_avg(self) -> float:
        n = self.sample_size
        return (self.confidence_sum / n) if n else 0.0

    @property
    def realized_win_rate(self) -> float:
        n = self.sample_size
        return (self.wins / n) if n else 0.0

    @property
    def avg_return_pct(self) -> float:
        return sum(self.returns) / len(self.returns) if self.returns else 0.0


class ConfidenceCalibrationEngine:
    """Analyse whether model confidence scores predict actual win rates.

    Parameters
    ----------
    db:
        Active SQLAlchemy Session.
    lookback_days:
        Calendar days of outcomes to include (default: 30).
    """

    def __init__(self, db: Session, lookback_days: int = 30) -> None:
        self._db = db
        self._lookback_days = lookback_days

    # ------------------------------------------------------------------

    def evaluate(self) -> ConfidenceCalibrationResult:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._lookback_days)

        rows: list[TradingSignalOutcome] = (
            self._db.query(TradingSignalOutcome)
            .filter(
                TradingSignalOutcome.signal_at >= cutoff,
                TradingSignalOutcome.outcome_correct.isnot(None),
                TradingSignalOutcome.confidence.isnot(None),
                TradingSignalOutcome.price_change_pct.isnot(None),
            )
            .all()
        )

        # Accumulate per bucket
        accs: dict[str, _BucketAcc] = {label: _BucketAcc() for label, _, _ in _BUCKETS}

        for row in rows:
            conf = int(row.confidence)  # type: ignore[arg-type]
            for label, lo, hi in _BUCKETS:
                if lo <= conf <= hi:
                    accs[label].add(conf, bool(row.outcome_correct), float(row.price_change_pct))
                    break

        # Build CalibrationBucket objects
        buckets: list[CalibrationBucket] = []
        calibrated_threshold: int | None = None

        for label, lo, hi in _BUCKETS:
            acc = accs[label]
            if acc.sample_size == 0:
                continue

            pred_avg = acc.predicted_confidence_avg
            realized = acc.realized_win_rate
            gap = realized - (pred_avg / 100.0)  # both on [0, 1] scale
            overconfident = gap < _OVERCONFIDENCE_GAP
            underconfident = gap > _UNDERCONFIDENCE_GAP

            buckets.append(CalibrationBucket(
                label=label,
                lower=lo,
                upper=hi,
                sample_size=acc.sample_size,
                predicted_confidence_avg=pred_avg,
                realized_win_rate=realized,
                calibration_gap=gap,
                avg_return_pct=acc.avg_return_pct,
                overconfident=overconfident,
                underconfident=underconfident,
            ))

            # Track lowest bucket where win_rate meets threshold
            if realized >= _CALIBRATED_WIN_RATE_THRESHOLD:
                if calibrated_threshold is None or lo < calibrated_threshold:
                    calibrated_threshold = lo

        # Slope: linear regression of predicted_confidence_avg → realized_win_rate
        # Simple Pearson-slope without numpy (advisory context).
        slope = self._compute_slope(buckets)

        overconfidence_warning = any(b.overconfident for b in buckets)
        underconfidence_warning = any(b.underconfident for b in buckets)

        # well_calibrated: slope exists and positive, no extreme overconfidence
        well_calibrated = (slope is not None and slope > 0 and not overconfidence_warning)

        recommended_min_confidence = calibrated_threshold  # could be refined downstream

        total_outcomes = sum(b.sample_size for b in buckets)

        logger.info(
            "adaptive.confidence_calibration evaluated",
            extra={
                "lookback_days": self._lookback_days,
                "total_outcomes": total_outcomes,
                "buckets": len(buckets),
                "calibrated_threshold": calibrated_threshold,
                "well_calibrated": well_calibrated,
                "slope": slope,
            },
        )

        return ConfidenceCalibrationResult(
            evaluated_at=datetime.now(timezone.utc),
            total_outcomes=total_outcomes,
            buckets=buckets,
            calibrated_threshold=calibrated_threshold,
            overall_calibration_slope=slope,
            well_calibrated=well_calibrated,
            overconfidence_warning=overconfidence_warning,
            underconfidence_warning=underconfidence_warning,
            recommended_min_confidence=recommended_min_confidence,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_slope(buckets: list[CalibrationBucket]) -> float | None:
        """Ordinary-least-squares slope: predicted_confidence_avg → realized_win_rate.

        Returns None if fewer than 2 buckets have data.
        """
        if len(buckets) < 2:
            return None

        xs = [b.predicted_confidence_avg for b in buckets]
        ys = [b.realized_win_rate for b in buckets]
        n = len(xs)
        x_mean = sum(xs) / n
        y_mean = sum(ys) / n

        numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(xs, ys))
        denominator = sum((xi - x_mean) ** 2 for xi in xs)
        if denominator == 0:
            return None
        return numerator / denominator
