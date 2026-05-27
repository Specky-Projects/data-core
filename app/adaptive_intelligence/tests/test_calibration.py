"""Tests for ConfidenceCalibrationEngine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.adaptive_intelligence.confidence_calibration import (
    ConfidenceCalibrationEngine,
    _BucketAcc,
    _BUCKETS,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_outcome(
    confidence: int = 75,
    outcome_correct: bool = True,
    price_change_pct: float = 1.0,
    days_ago: int = 1,
):
    obj = MagicMock()
    obj.confidence = confidence
    obj.outcome_correct = outcome_correct
    obj.price_change_pct = price_change_pct
    obj.signal_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return obj


def _make_engine(rows: list) -> ConfidenceCalibrationEngine:
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = rows
    return ConfidenceCalibrationEngine(db, lookback_days=30)


# ── BucketAcc unit tests ───────────────────────────────────────────────────────

class TestBucketAcc:
    def test_empty_bucket(self):
        acc = _BucketAcc()
        assert acc.sample_size == 0
        assert acc.realized_win_rate == 0.0
        assert acc.predicted_confidence_avg == 0.0

    def test_single_correct(self):
        acc = _BucketAcc()
        acc.add(70, True, 1.0)
        assert acc.sample_size == 1
        assert acc.wins == 1
        assert acc.realized_win_rate == 1.0
        assert acc.predicted_confidence_avg == 70.0

    def test_mixed_outcomes(self):
        acc = _BucketAcc()
        for _ in range(3):
            acc.add(80, True, 1.0)
        for _ in range(2):
            acc.add(80, False, -0.5)
        assert acc.realized_win_rate == pytest.approx(0.6)

    def test_avg_return_pct(self):
        acc = _BucketAcc()
        acc.add(70, True, 2.0)
        acc.add(70, False, -1.0)
        assert acc.avg_return_pct == pytest.approx(0.5)


# ── Engine integration tests ───────────────────────────────────────────────────

class TestConfidenceCalibrationEngine:
    def test_empty_db_returns_empty_result(self):
        engine = _make_engine([])
        result = engine.evaluate()
        assert result.total_outcomes == 0
        assert result.buckets == []
        assert result.calibrated_threshold is None
        assert result.overall_calibration_slope is None
        assert not result.well_calibrated

    def test_single_bucket_no_slope(self):
        """Only one bucket populated → slope cannot be computed."""
        rows = [_make_outcome(confidence=75, outcome_correct=True) for _ in range(10)]
        engine = _make_engine(rows)
        result = engine.evaluate()
        assert len(result.buckets) == 1
        assert result.overall_calibration_slope is None  # need >= 2 buckets

    def test_two_buckets_positive_slope(self):
        """Higher confidence bucket has higher win rate → positive slope.

        For well_calibrated=True the buckets must also not be overconfident,
        meaning each bucket's realized win_rate should be roughly in line with
        its predicted confidence (gap > _OVERCONFIDENCE_GAP = -0.10).

        Setup:
          - 21-40 bucket: confidence=30, 3 correct / 7 wrong → wr=0.30, gap=0.30-0.30=0.00 ✓
          - 81-100 bucket: confidence=85, 8 correct / 2 wrong → wr=0.80, gap=0.80-0.85=-0.05 ✓
        """
        low_conf_rows = (
            [_make_outcome(confidence=30, outcome_correct=True) for _ in range(3)] +
            [_make_outcome(confidence=30, outcome_correct=False) for _ in range(7)]
        )
        high_conf_rows = (
            [_make_outcome(confidence=85, outcome_correct=True) for _ in range(8)] +
            [_make_outcome(confidence=85, outcome_correct=False) for _ in range(2)]
        )
        engine = _make_engine(low_conf_rows + high_conf_rows)
        result = engine.evaluate()
        assert result.overall_calibration_slope is not None
        assert result.overall_calibration_slope > 0
        assert result.well_calibrated

    def test_two_buckets_negative_slope_not_well_calibrated(self):
        """Higher confidence bucket has LOWER win rate → negative slope → not calibrated."""
        low_conf_rows = [_make_outcome(confidence=30, outcome_correct=True) for _ in range(10)]
        high_conf_rows = [_make_outcome(confidence=85, outcome_correct=False) for _ in range(10)]
        engine = _make_engine(low_conf_rows + high_conf_rows)
        result = engine.evaluate()
        assert result.overall_calibration_slope is not None
        assert result.overall_calibration_slope < 0
        assert not result.well_calibrated

    def test_calibrated_threshold_set_when_bucket_above_55_pct(self):
        """Bucket with realized win_rate >= 55% sets calibrated_threshold."""
        rows = [_make_outcome(confidence=75, outcome_correct=True) for _ in range(8)]
        rows += [_make_outcome(confidence=75, outcome_correct=False) for _ in range(2)]
        engine = _make_engine(rows)
        result = engine.evaluate()
        assert result.calibrated_threshold == 61  # 61-80 bucket lower bound

    def test_calibrated_threshold_none_when_no_bucket_above_55(self):
        rows = [_make_outcome(confidence=75, outcome_correct=False) for _ in range(10)]
        engine = _make_engine(rows)
        result = engine.evaluate()
        assert result.calibrated_threshold is None

    def test_overconfidence_warning_when_gap_negative(self):
        """predicted >> realized → overconfident bucket → warning."""
        # confidence=90 but all wrong → realized=0, predicted≈90 → gap ≈ -0.90
        rows = [_make_outcome(confidence=90, outcome_correct=False) for _ in range(10)]
        engine = _make_engine(rows)
        result = engine.evaluate()
        assert result.overconfidence_warning

    def test_underconfidence_warning_when_gap_positive(self):
        """predicted << realized → underconfident."""
        # confidence=10 but all correct → realized=1.0, predicted≈10 → gap ≈ +0.90
        rows = [_make_outcome(confidence=10, outcome_correct=True) for _ in range(10)]
        engine = _make_engine(rows)
        result = engine.evaluate()
        assert result.underconfidence_warning

    def test_well_calibrated_false_when_overconfident(self):
        """Even with positive slope, overconfidence flags prevent well_calibrated=True."""
        # Build: low bucket good (positive slope), but high bucket overconfident
        low_rows = [_make_outcome(confidence=30, outcome_correct=True) for _ in range(10)]
        high_rows = [_make_outcome(confidence=90, outcome_correct=False) for _ in range(10)]
        engine = _make_engine(low_rows + high_rows)
        result = engine.evaluate()
        assert not result.well_calibrated

    def test_bucket_boundaries_correct(self):
        """Confidence=20 → bucket '0-20'; confidence=21 → bucket '21-40'."""
        at_20 = [_make_outcome(confidence=20, outcome_correct=True) for _ in range(5)]
        at_21 = [_make_outcome(confidence=21, outcome_correct=True) for _ in range(5)]
        engine = _make_engine(at_20 + at_21)
        result = engine.evaluate()
        labels = {b.label for b in result.buckets}
        assert "0-20" in labels
        assert "21-40" in labels

    def test_recommended_min_confidence_equals_calibrated_threshold(self):
        rows = [_make_outcome(confidence=75, outcome_correct=True) for _ in range(8)]
        rows += [_make_outcome(confidence=75, outcome_correct=False) for _ in range(2)]
        engine = _make_engine(rows)
        result = engine.evaluate()
        assert result.recommended_min_confidence == result.calibrated_threshold

    def test_total_outcomes_sum_of_buckets(self):
        rows = [_make_outcome(confidence=30) for _ in range(5)]
        rows += [_make_outcome(confidence=75) for _ in range(7)]
        engine = _make_engine(rows)
        result = engine.evaluate()
        assert result.total_outcomes == sum(b.sample_size for b in result.buckets)
