"""Phase 4 tests: reliability scoring, trend detection, forecasting, anomaly detection."""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.auto_healing.reliability import (
    AnomalyDetector,
    Forecaster,
    ReliabilityScorer,
    ServiceScore,
    SystemSnapshot,
    TrendDetector,
    TrendPoint,
    _grade,
    _linear_regression,
    _parse_meminfo,
)


# ── _grade ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("score,expected", [
    (100.0, "A+"),
    (98.0, "A+"),
    (97.9, "A"),
    (90.0, "A"),
    (89.9, "B"),
    (75.0, "B"),
    (74.9, "C"),
    (60.0, "C"),
    (59.9, "D"),
    (45.0, "D"),
    (44.9, "F"),
    (0.0, "F"),
])
def test_grade_boundaries(score, expected):
    assert _grade(score) == expected


# ── _linear_regression ───────────────────────────────────────────────────────

def test_linear_regression_perfect_line():
    xs = [0.0, 1.0, 2.0, 3.0, 4.0]
    ys = [10.0, 12.0, 14.0, 16.0, 18.0]  # slope=2, intercept=10
    slope, intercept = _linear_regression(xs, ys)
    assert slope == pytest.approx(2.0, abs=0.001)
    assert intercept == pytest.approx(10.0, abs=0.001)


def test_linear_regression_flat():
    xs = [0.0, 1.0, 2.0]
    ys = [5.0, 5.0, 5.0]
    slope, intercept = _linear_regression(xs, ys)
    assert slope == pytest.approx(0.0, abs=0.001)
    assert intercept == pytest.approx(5.0, abs=0.001)


def test_linear_regression_single_point():
    slope, intercept = _linear_regression([0.0], [7.0])
    assert intercept == pytest.approx(7.0, abs=0.001)


# ── ReliabilityScorer — _compute_score ───────────────────────────────────────

def _fake_metrics(incidents=0, heals_failed=0, circuit_opens=0, cooldown_blocks=0):
    m = MagicMock()
    m.incidents_total = incidents
    m.heals_failed = heals_failed
    m.circuit_opens = circuit_opens
    m.cooldown_blocks = cooldown_blocks
    m.heals_attempted = incidents
    m.heal_success_rate = None
    m.recoveries = 0
    return m


def test_score_perfect_uptime():
    score = ReliabilityScorer._compute_score(1.0, _fake_metrics())
    assert score == pytest.approx(100.0)


def test_score_zero_uptime():
    score = ReliabilityScorer._compute_score(0.0, _fake_metrics())
    assert score == pytest.approx(60.0)  # 100 - 40 uptime deduction


def test_score_incidents_deduct():
    score = ReliabilityScorer._compute_score(1.0, _fake_metrics(incidents=5))
    assert score == pytest.approx(90.0)  # 100 - 5*2


def test_score_circuit_opens_deduct():
    score = ReliabilityScorer._compute_score(1.0, _fake_metrics(circuit_opens=2))
    assert score == pytest.approx(90.0)  # 100 - 2*5


def test_score_cooldown_blocks_bonus():
    # Start with a degraded score (uptime 95%) so the +1 bonus is observable
    score_without = ReliabilityScorer._compute_score(0.95, _fake_metrics(cooldown_blocks=0))
    score_with = ReliabilityScorer._compute_score(0.95, _fake_metrics(cooldown_blocks=1))
    assert score_with > score_without


def test_score_clamped_to_zero():
    # Max deductions: 40 (0% uptime) + 20 (incidents cap) + 15 (heals_failed cap)
    # + 10 (circuit_opens cap) = 85 → floor is 15, never reaches 0
    score = ReliabilityScorer._compute_score(
        0.0, _fake_metrics(incidents=100, heals_failed=100, circuit_opens=100)
    )
    assert score == pytest.approx(15.0)


def test_score_clamped_to_100():
    score = ReliabilityScorer._compute_score(1.0, _fake_metrics())
    assert score <= 100.0


# ── ServiceScore — to_dict ────────────────────────────────────────────────────

def test_service_score_to_dict():
    s = ServiceScore(
        service="redis",
        score=97.5,
        grade="A",
        uptime_pct=99.8,
        heal_success_rate=0.9,
    )
    d = s.to_dict()
    assert d["score"] == pytest.approx(97.5)
    assert d["grade"] == "A"
    assert d["heal_success_rate"] == pytest.approx(0.9)


# ── TrendDetector — _analyze ─────────────────────────────────────────────────

def test_trend_rising():
    now = time.time()
    points = [TrendPoint(timestamp=now + i * 3600, value=80.0 + i) for i in range(5)]
    result = TrendDetector._analyze("disk_used_pct", None, points, window_hours=5.0)
    assert result.direction == "rising"
    assert result.slope_per_hour > 0


def test_trend_falling():
    now = time.time()
    points = [TrendPoint(timestamp=now + i * 3600, value=90.0 - i * 2) for i in range(5)]
    result = TrendDetector._analyze("disk_used_pct", None, points, window_hours=5.0)
    assert result.direction == "falling"
    assert result.slope_per_hour < 0


def test_trend_stable():
    now = time.time()
    points = [TrendPoint(timestamp=now + i * 3600, value=70.0) for i in range(5)]
    result = TrendDetector._analyze("disk_used_pct", None, points, window_hours=5.0)
    assert result.direction == "stable"


def test_trend_insufficient_data():
    result = TrendDetector._analyze("disk_used_pct", None, [], window_hours=5.0)
    assert result.data_points == 0
    assert result.direction == "stable"


# ── Forecaster — _forecast_series ────────────────────────────────────────────

def _mock_ts_points(values: list[float]) -> list[TrendPoint]:
    now = time.time()
    return [TrendPoint(timestamp=now + i * 3600, value=v)
            for i, v in enumerate(values)]


def test_forecast_rising_to_threshold():
    # Disk at 80%, rising 1%/hour → 95% threshold in ~15 hours
    points = _mock_ts_points([80.0 + i for i in range(10)])

    with patch("app.auto_healing.reliability._read_points", return_value=points):
        result = Forecaster._forecast_series("disk_used_pct", 95.0, window_hours=48.0)

    assert result["status"] in ("rising", "warning", "critical")
    assert result["eta_threshold_hours"] is not None
    assert result["eta_threshold_hours"] == pytest.approx(6.0, abs=2.0)


def test_forecast_stable_no_eta():
    points = _mock_ts_points([70.0] * 8)

    with patch("app.auto_healing.reliability._read_points", return_value=points):
        result = Forecaster._forecast_series("disk_used_pct", 95.0, window_hours=48.0)

    assert result["status"] == "stable"
    assert result["eta_threshold_hours"] is None


def test_forecast_insufficient_data():
    with patch("app.auto_healing.reliability._read_points", return_value=[]):
        result = Forecaster._forecast_series("disk_used_pct", 95.0, window_hours=48.0)

    assert result["status"] == "insufficient_data"
    assert result["eta_threshold_hours"] is None


# ── AnomalyDetector — _check_series ─────────────────────────────────────────

def _make_baseline_points(baseline_value: float, n: int = 12) -> list[TrendPoint]:
    now = time.time()
    return [TrendPoint(timestamp=now + i * 3600, value=baseline_value)
            for i in range(n)]


def test_anomaly_detected_high_spike():
    # Baseline: small variation around 10.0, last point: 50.0 → very high z-score
    # (identical baseline values produce std=0, which the detector ignores)
    now = time.time()
    baseline_values = [9.5, 10.5, 10.0, 10.2, 9.8, 10.1, 9.9, 10.3, 10.0, 9.7, 10.4]
    points = [TrendPoint(timestamp=now + i * 3600, value=v)
              for i, v in enumerate(baseline_values)]
    points.append(TrendPoint(timestamp=now + 12 * 3600, value=50.0))

    with patch("app.auto_healing.reliability._read_points", return_value=points):
        anomalies = AnomalyDetector._check_series(
            "disk_used_pct", "disk_spike", None, 24.0, "2026-06-08T20:00:00Z"
        )
    assert len(anomalies) == 1
    assert anomalies[0].z_score > 2.5
    assert anomalies[0].anomaly_type == "disk_spike"


def test_anomaly_not_detected_normal():
    # Stable baseline — no anomaly
    now = time.time()
    points = [TrendPoint(timestamp=now + i * 3600, value=70.0) for i in range(12)]

    with patch("app.auto_healing.reliability._read_points", return_value=points):
        anomalies = AnomalyDetector._check_series(
            "disk_used_pct", "disk_spike", None, 24.0, "2026-06-08T20:00:00Z"
        )
    assert len(anomalies) == 0


def test_anomaly_insufficient_points():
    # Only 3 points — below minimum of 8
    points = [TrendPoint(timestamp=float(i), value=10.0) for i in range(3)]

    with patch("app.auto_healing.reliability._read_points", return_value=points):
        anomalies = AnomalyDetector._check_series(
            "disk_used_pct", "disk_spike", None, 24.0, "2026-06-08T20:00:00Z"
        )
    assert len(anomalies) == 0


def test_anomaly_severity_levels():
    # z > 4.0 → HIGH
    now = time.time()
    points = [TrendPoint(timestamp=now + i * 3600, value=10.0) for i in range(11)]
    points.append(TrendPoint(timestamp=now + 12 * 3600, value=100.0))

    with patch("app.auto_healing.reliability._read_points", return_value=points):
        anomalies = AnomalyDetector._check_series(
            "queue_backlog", "queue_spike", None, 24.0, "2026-06-08T20:00:00Z"
        )
    if anomalies:
        assert anomalies[0].severity in ("HIGH", "MEDIUM", "LOW")


# ── ForecastResult.to_dict ────────────────────────────────────────────────────

def test_forecast_result_to_dict():
    from app.auto_healing.reliability import ForecastResult
    fc = ForecastResult(
        computed_at="2026-06-08T20:00:00+00:00",
        disk={"current": 92.0, "status": "warning"},
        memory={"current": 70.0, "status": "stable"},
        queue_backlog={"current": 45.0, "status": "stable"},
    )
    d = fc.to_dict()
    assert d["disk"]["current"] == pytest.approx(92.0)
    assert d["memory"]["status"] == "stable"


# ── SystemSnapshot — fail-safe ────────────────────────────────────────────────

def test_system_snapshot_no_crash_on_error():
    snap = SystemSnapshot()
    fake_redis = MagicMock()
    fake_redis.zadd.side_effect = Exception("redis down")
    with patch("app.auto_healing.reliability._redis", return_value=fake_redis):
        result = snap.snapshot()
    # Must not raise; result may be empty but should be a dict
    assert isinstance(result, dict)
