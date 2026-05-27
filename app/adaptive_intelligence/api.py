"""Adaptive Intelligence Layer — FastAPI router.

All endpoints are public (advisory/read-only — no trading side-effects).
Downstream consumers: dashboards, PolicyContract generator, operators.

Prefix: /adaptive-intelligence
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.adaptive_intelligence.orchestrator import AdaptiveIntelligenceOrchestrator
from app.adaptive_intelligence.dto import AdaptiveIntelligenceReport
from core.config import settings
from database.session import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/adaptive-intelligence", tags=["adaptive-intelligence"])


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Full report ────────────────────────────────────────────────────────────────

@router.get(
    "/report",
    summary="Full Adaptive Intelligence report",
    response_model=AdaptiveIntelligenceReport,
)
def get_full_report(
    lookback_days: int = Query(default=30, ge=1, le=180, description="Lookback window in calendar days"),
    db: Session = Depends(_get_db),
) -> AdaptiveIntelligenceReport:
    """Runs all four adaptive intelligence engines and returns the combined report.

    **Advisory-only** — never alters trading state.

    Engines:
    - **StrategyFeedbackEngine** — per-slice win rate, expectancy, profit factor
    - **ConfidenceCalibrationEngine** — bucket-by-bucket confidence calibration
    - **RegimeAdapter** — per-regime×signal performance analysis
    - **RiskTuner** — aggregate risk level + policy hints for enforcement layer
    """
    orch = AdaptiveIntelligenceOrchestrator(
        db=db,
        lookback_days=lookback_days,
        environment=settings.app_env,
    )
    return orch.evaluate()


# ── Summary ────────────────────────────────────────────────────────────────────

@router.get(
    "/summary",
    summary="Compact advisory summary",
    response_model=dict,
)
def get_summary(
    lookback_days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Returns a compact advisory summary suitable for quick operator review
    or upstream enforcement hint consumption.

    Equivalent to ``/report`` but only the fields in
    :meth:`AdaptiveIntelligenceReport.to_summary`.
    """
    orch = AdaptiveIntelligenceOrchestrator(
        db=db,
        lookback_days=lookback_days,
        environment=settings.app_env,
    )
    report = orch.evaluate()
    return report.to_summary()


# ── Strategy feedback only ────────────────────────────────────────────────────

@router.get(
    "/strategy-feedback",
    summary="Strategy feedback slices",
    response_model=dict,
)
def get_strategy_feedback(
    lookback_days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Strategy performance by (symbol, timeframe, regime, signal) slice.

    Returns recommendation breakdowns, top performers, and underperformers
    without running the full orchestration (faster).
    """
    from app.adaptive_intelligence.strategy_feedback import StrategyFeedbackEngine
    result = StrategyFeedbackEngine(db, lookback_days).evaluate()
    return result.model_dump(mode="json")


# ── Confidence calibration only ───────────────────────────────────────────────

@router.get(
    "/calibration",
    summary="Confidence calibration buckets",
    response_model=dict,
)
def get_calibration(
    lookback_days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Confidence calibration analysis per bucket (0-20, 21-40, 41-60, 61-80, 81-100).

    Indicates whether model confidence scores are predictive of actual win rates.
    """
    from app.adaptive_intelligence.confidence_calibration import ConfidenceCalibrationEngine
    result = ConfidenceCalibrationEngine(db, lookback_days).evaluate()
    return result.model_dump(mode="json")


# ── Regime adapter only ───────────────────────────────────────────────────────

@router.get(
    "/regime",
    summary="Regime adaptation recommendations",
    response_model=dict,
)
def get_regime(
    lookback_days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Per-regime×signal×symbol adaptation recommendations.

    Shows which regime / direction combinations are performing well or poorly.
    """
    from app.adaptive_intelligence.regime_adapter import RegimeAdapter
    result = RegimeAdapter(db, lookback_days).evaluate()
    return result.model_dump(mode="json")


# ── Risk tuning hints ─────────────────────────────────────────────────────────

@router.get(
    "/risk",
    summary="Risk tuning hints",
    response_model=dict,
)
def get_risk(
    lookback_days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Returns the full risk tuning result including policy_hints.

    ``policy_hints`` is a structured dict consumed by the Enforcement
    PolicyContract generator to automatically adjust enforcement mode,
    position sizing, and confidence thresholds.

    Runs all engines internally to produce a coherent risk picture.
    """
    orch = AdaptiveIntelligenceOrchestrator(
        db=db,
        lookback_days=lookback_days,
        environment=settings.app_env,
    )
    report = orch.evaluate()
    return report.risk.model_dump(mode="json")
