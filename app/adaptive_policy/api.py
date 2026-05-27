"""Adaptive Policy Contract — FastAPI router.

All endpoints are public (advisory/read-only, no trading side-effects).

Prefix: /adaptive-policy

Endpoints:
  GET /adaptive-policy/report   — full AdaptivePolicyContract (JSON)
  GET /adaptive-policy/summary  — compact summary dict
  GET /adaptive-policy/hints    — enforcement_hints only (fast path)
  GET /adaptive-policy/mode     — current mode + rollout phase
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.adaptive_intelligence.orchestrator import AdaptiveIntelligenceOrchestrator
from app.adaptive_policy.dto import AdaptivePolicyContract
from app.adaptive_policy.generator import AdaptivePolicyGenerator, _safe_fallback
from app.adaptive_policy import metrics as policy_metrics
from app.adaptive_policy.rollout import RolloutModeManager
from core.config import settings
from database.session import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/adaptive-policy", tags=["adaptive-policy"])


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_rollout_phase() -> int:
    return getattr(settings, "adaptive_policy_rollout_phase", 1)


def _build_contract(
    db: Session,
    lookback_days: int,
    include_truth: bool = True,
) -> AdaptivePolicyContract:
    """Orchestrate AI + Truth → AdaptivePolicyContract."""
    t0 = time.perf_counter()
    rollout_phase = _get_rollout_phase()
    environment = settings.app_env

    # ── Adaptive Intelligence ─────────────────────────────────────────────────
    try:
        ai_report = AdaptiveIntelligenceOrchestrator(
            db=db,
            lookback_days=lookback_days,
            environment=environment,
        ).evaluate()
    except Exception as exc:
        logger.exception("adaptive_policy.api: AI orchestration failed: %s", exc)
        return _safe_fallback(environment, rollout_phase, f"AI orchestration failed: {exc}")

    # ── Operational Truth (optional) ──────────────────────────────────────────
    truth_report = None
    if include_truth:
        try:
            from app.operational_truth.production_readiness import ProductionReadinessService
            truth_report = ProductionReadinessService(db).evaluate()
        except Exception as exc:
            logger.warning(
                "adaptive_policy.api: truth report unavailable: %s — using conservative defaults", exc
            )

    # ── Generate contract ─────────────────────────────────────────────────────
    generator = AdaptivePolicyGenerator(
        rollout_phase=rollout_phase,
        environment=environment,
    )
    contract = generator.generate(ai_report=ai_report, truth_report=truth_report)

    # ── Publish metrics ───────────────────────────────────────────────────────
    elapsed = time.perf_counter() - t0
    try:
        policy_metrics.publish_contract(contract)
        policy_metrics.adaptive_policy_generation_duration_seconds.observe(elapsed)
    except Exception:
        pass

    return contract


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/report",
    summary="Full Adaptive Policy Contract",
    response_model=AdaptivePolicyContract,
)
def get_report(
    lookback_days: int = Query(default=30, ge=1, le=180, description="Lookback window in calendar days"),
    include_truth: bool = Query(default=True, description="Include Operational Truth report (slower)"),
    db: Session = Depends(_get_db),
) -> AdaptivePolicyContract:
    """Full AdaptivePolicyContract synthesising Adaptive Intelligence + Operational Truth.

    **Advisory-only** — the contract never directly blocks trading.

    Rollout phase (set via ``ADAPTIVE_POLICY_ROLLOUT_PHASE`` env var):
    - Phase 1: OBSERVE_ONLY — log only
    - Phase 2: WARN_ONLY — warn on degraded conditions
    - Phase 3: SAFE_MODE_HINTS — may recommend safe_mode
    - Phase 4: FAIL_CLOSED_CRITICAL_ONLY — FAIL_CLOSED on CRITICAL risk only
    """
    return _build_contract(db, lookback_days, include_truth)


@router.get(
    "/summary",
    summary="Compact policy summary",
    response_model=dict,
)
def get_summary(
    lookback_days: int = Query(default=30, ge=1, le=180),
    include_truth: bool = Query(default=True),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Compact summary for operator dashboards and quick health checks."""
    contract = _build_contract(db, lookback_days, include_truth)
    return contract.to_summary()


@router.get(
    "/hints",
    summary="Enforcement hints only",
    response_model=dict,
)
def get_hints(
    lookback_days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Fast path returning only enforcement_hints + boost_blocked status.

    Suitable for high-frequency polling by downstream enforcement components.
    Skips Operational Truth evaluation for speed.
    """
    contract = _build_contract(db, lookback_days, include_truth=False)
    return {
        "enforcement_hints": contract.enforcement_hints.model_dump(),
        "boost_blocked": contract.boost_blocked,
        "boost_block_reasons": contract.boost_block_reasons,
        "mode": contract.mode,
        "risk_level": contract.risk_level,
        "suggested_position_size_multiplier": contract.suggested_position_size_multiplier,
        "suggested_min_confidence": contract.suggested_min_confidence,
        "generated_at": contract.generated_at.isoformat(),
        "expires_at": contract.expires_at.isoformat(),
    }


@router.get(
    "/mode",
    summary="Current policy mode and rollout info",
    response_model=dict,
)
def get_mode(
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Returns current rollout phase metadata without running the full evaluation.

    Useful for tooling that needs to know the rollout state without paying
    the evaluation cost.
    """
    rollout_phase = _get_rollout_phase()
    mgr = RolloutModeManager(rollout_phase)
    return {
        "rollout": mgr.describe(),
        "adaptive_policy_enabled": getattr(settings, "adaptive_policy_enabled", True),
        "environment": settings.app_env,
    }
