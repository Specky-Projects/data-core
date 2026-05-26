"""Dataset integrity scoring for crypto/trading candles.

Combines freshness, coverage, and OHLC consistency into a single 0-100 score,
persists it to ``crypto_dataset_quality_scores``, and emits Prometheus metrics.

Score breakdown:
  - Freshness  : 0-40 pts  (full score when staleness ≤ 1× interval; linear decay to 2×)
  - Coverage   : 0-40 pts  (proportional to coverage_pct in the last 24h)
  - OHLC valid : 0-20 pts  (pass/fail based on DataQualityService "trading" rules)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.data_quality.crypto.coverage import CandleCoverageAnalyzer, CoverageResult
from app.data_quality.crypto.freshness import CandleFreshnessValidator, FreshnessResult
from app.data_quality.crypto.models import CryptoDatasetQualityScore
from app.data_quality.services import DataQualityService

logger = logging.getLogger(__name__)

# Prometheus metrics — imported lazily to avoid circular imports at module load.
# api.metrics registers them; this module calls them.
_metrics_loaded = False
_dataset_integrity_score = None
_candle_coverage_pct = None
_stale_candle_total = None
_candle_gap_total = None


def _load_metrics() -> None:
    global _metrics_loaded, _dataset_integrity_score, _candle_coverage_pct
    global _stale_candle_total, _candle_gap_total
    if _metrics_loaded:
        return
    try:
        from api.metrics import (  # noqa: PLC0415
            candle_coverage_pct,
            candle_gap_total,
            dataset_integrity_score,
            stale_candle_total,
        )
        _dataset_integrity_score = dataset_integrity_score
        _candle_coverage_pct = candle_coverage_pct
        _stale_candle_total = stale_candle_total
        _candle_gap_total = candle_gap_total
        _metrics_loaded = True
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not load Prometheus metrics (non-fatal): %s", exc)


@dataclass
class IntegrityScore:
    """Composite integrity report for one symbol/timeframe pair."""

    symbol: str
    timeframe: str
    score: float  # 0.0-100.0
    freshness_score: float  # 0-40
    coverage_score: float   # 0-40
    ohlc_score: float       # 0-20
    staleness_hours: float
    coverage_pct: float
    gap_count: int
    candles_24h: int
    expected_candles_24h: int
    components: dict[str, Any] = field(default_factory=dict)


class DatasetIntegrityScorer:
    """Scores the integrity of candle data per symbol/timeframe.

    Orchestrates freshness validation, coverage analysis, and OHLC rule checks
    into a single 0-100 composite score, then persists the result and emits
    Prometheus metrics.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._freshness = CandleFreshnessValidator(db)
        self._coverage = CandleCoverageAnalyzer(db)
        _load_metrics()

    def score(
        self,
        symbols: list[str],
        timeframes: list[str],
        *,
        persist: bool = True,
        emit_metrics: bool = True,
    ) -> list[IntegrityScore]:
        """Compute IntegrityScore for every (symbol, timeframe) pair.

        Args:
            symbols: List of trading pair symbols (e.g. ["BTC/USDT", "SOL/USDT"]).
            timeframes: List of timeframes (e.g. ["15m", "1h"]).
            persist: Write scores to ``crypto_dataset_quality_scores``.
            emit_metrics: Update Prometheus gauges/counters.

        Returns:
            List of IntegrityScore dataclasses, one per (symbol, timeframe) pair.
        """
        freshness_results = {
            (r.symbol, r.timeframe): r
            for r in self._freshness.check(symbols, timeframes)
        }
        coverage_results = {
            (r.symbol, r.timeframe): r
            for r in self._coverage.analyze(symbols, timeframes)
        }

        # OHLC consistency from the existing DataQualityService ("trading" module)
        ohlc_quality = self._get_ohlc_score()

        scores: list[IntegrityScore] = []
        for symbol in symbols:
            for timeframe in timeframes:
                key = (symbol, timeframe)
                freshness = freshness_results.get(key)
                coverage = coverage_results.get(key)
                integrity = self._compute_score(symbol, timeframe, freshness, coverage, ohlc_quality)
                scores.append(integrity)

                if persist:
                    self._persist(integrity)
                if emit_metrics:
                    self._emit(integrity)

        if persist:
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

        return scores

    # ── Private helpers ────────────────────────────────────────────────────────

    def _get_ohlc_score(self) -> float:
        """Return OHLC pass rate (0.0-1.0) from DataQualityService for the trading module."""
        try:
            result = DataQualityService(self.db).run(module="trading", limit=500)
            runs = result.get("runs", [])
            if runs:
                qs = runs[0].get("quality_score")
                if qs is not None:
                    return float(qs)
        except Exception as exc:
            logger.debug("OHLC quality check failed (non-fatal): %s", exc)
        return 1.0  # assume perfect if check unavailable

    def _compute_score(
        self,
        symbol: str,
        timeframe: str,
        freshness: FreshnessResult | None,
        coverage: CoverageResult | None,
        ohlc_pass_rate: float,
    ) -> IntegrityScore:
        # ── Freshness score (0-40 pts) ─────────────────────────────────────────
        freshness_pts = 0.0
        staleness_hours = float("inf")
        gap_count = 0
        candles_24h = 0
        expected_24h = 0

        if freshness:
            staleness_hours = freshness.staleness_hours
            gap_count = freshness.gap_count
            candles_24h = freshness.candles_in_window
            interval = freshness.expected_interval_hours

            if freshness.status == "missing":
                freshness_pts = 0.0
            elif staleness_hours <= interval:
                freshness_pts = 40.0
            elif staleness_hours <= interval * 2:
                # Linear decay: 40 → 0 between 1× and 2× interval
                ratio = 1.0 - (staleness_hours - interval) / interval
                freshness_pts = round(40.0 * max(0.0, ratio), 2)
            else:
                freshness_pts = 0.0

        # ── Coverage score (0-40 pts) ──────────────────────────────────────────
        coverage_pct = 0.0
        if coverage:
            coverage_pct = coverage.coverage_pct
            expected_24h = coverage.expected_candles_24h
            candles_24h = coverage.candles_24h
            coverage_pts = round(40.0 * min(1.0, coverage_pct / 100.0), 2)
        else:
            coverage_pts = 0.0

        # ── OHLC score (0-20 pts) ──────────────────────────────────────────────
        ohlc_pts = round(20.0 * ohlc_pass_rate, 2)

        total = round(freshness_pts + coverage_pts + ohlc_pts, 2)

        return IntegrityScore(
            symbol=symbol,
            timeframe=timeframe,
            score=total,
            freshness_score=freshness_pts,
            coverage_score=coverage_pts,
            ohlc_score=ohlc_pts,
            staleness_hours=round(staleness_hours if staleness_hours != float("inf") else 9999.0, 2),
            coverage_pct=coverage_pct,
            gap_count=gap_count,
            candles_24h=candles_24h,
            expected_candles_24h=expected_24h,
            components={
                "freshness_status": freshness.status if freshness else "unknown",
                "staleness_hours": round(staleness_hours if staleness_hours != float("inf") else 9999.0, 2),
                "coverage_pct": coverage_pct,
                "gap_count": gap_count,
                "ohlc_pass_rate": ohlc_pass_rate,
                "freshness_pts": freshness_pts,
                "coverage_pts": coverage_pts,
                "ohlc_pts": ohlc_pts,
            },
        )

    def _persist(self, s: IntegrityScore) -> None:
        row = CryptoDatasetQualityScore(
            symbol=s.symbol,
            timeframe=s.timeframe,
            integrity_score=s.score,
            freshness_score=s.freshness_score,
            coverage_score=s.coverage_score,
            ohlc_score=s.ohlc_score,
            staleness_hours=s.staleness_hours,
            coverage_pct=s.coverage_pct,
            gap_count=s.gap_count,
            total_candles_24h=s.candles_24h,
            expected_candles_24h=s.expected_candles_24h,
            components_json=s.components,
            evaluated_at=datetime.now(tz=timezone.utc),
        )
        self.db.add(row)

    def _emit(self, s: IntegrityScore) -> None:
        if not _metrics_loaded:
            return
        try:
            labels = {"symbol": s.symbol, "timeframe": s.timeframe}
            _dataset_integrity_score.labels(**labels).set(s.score)
            _candle_coverage_pct.labels(**labels).set(s.coverage_pct)
            if s.components.get("freshness_status") in ("stale", "missing"):
                _stale_candle_total.labels(**labels).inc()
            if s.gap_count > 0:
                _candle_gap_total.labels(**labels).inc(s.gap_count)
        except Exception as exc:
            logger.debug("Prometheus emit failed (non-fatal): %s", exc)
