"""Policy endpoint — GET /policy/operational.

Returns a versioned OperationalPolicyContract for downstream enforcement clients.
This endpoint is intentionally public (no auth) — it publishes safety decisions,
not sensitive data, and must be reachable by peer services without API keys.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.operational_truth.policy.contract import OperationalPolicyContract
from app.operational_truth.policy.generator import generate_policy
from app.operational_truth.production_readiness import ProductionReadinessService
from database.session import get_db

router = APIRouter(tags=["operational-policy"])

# HTTP status codes mapped to enforcement mode
_MODE_HTTP: dict[str, int] = {
    "observe_only":           200,
    "warn_only":              200,
    "safe_mode":              200,
    "fail_closed":            200,  # always 200 — the contract itself carries the decision
    "emergency_kill_switch":  200,
}


@router.get(
    "/policy/operational",
    response_model=OperationalPolicyContract,
    summary="Versioned operational policy contract for downstream enforcement",
    description=(
        "Returns a short-lived (2-min TTL) policy contract that encodes the current "
        "operational confidence level, enforcement mode, and allowed/blocked actions. "
        "Consumers should cache this contract and treat an expired or unreachable response "
        "as a signal to activate their local fallback (safe_mode)."
    ),
)
def get_operational_policy(db: Session = Depends(get_db)) -> JSONResponse:
    report = ProductionReadinessService(db).evaluate()
    contract = generate_policy(report)
    return JSONResponse(
        contract.model_dump(mode="json"),
        status_code=200,
        headers={
            "Cache-Control": f"public, max-age=60",
            "X-Enforcement-Mode": contract.enforcement_mode,
            "X-Confidence-Score": str(contract.confidence_score),
            "X-Contract-Version": contract.version,
        },
    )


@router.get(
    "/policy/summary",
    summary="Lightweight policy summary (enforcement mode + blocked actions only)",
)
def get_policy_summary(db: Session = Depends(get_db)) -> JSONResponse:
    """Fast endpoint for health checks and dashboards — skips full report details."""
    report = ProductionReadinessService(db).evaluate()
    contract = generate_policy(report)
    return JSONResponse({
        "version": contract.version,
        "enforcement_mode": contract.enforcement_mode,
        "confidence_score": contract.confidence_score,
        "safe_mode": contract.safe_mode,
        "fail_closed": contract.fail_closed,
        "kill_switch": contract.kill_switch,
        "blocked_actions": contract.blocked_actions,
        "position_size_multiplier": contract.position_size_multiplier,
        "min_confidence_override": contract.min_confidence_override,
        "expires_at": contract.expires_at.isoformat(),
        "generated_at": contract.generated_at.isoformat(),
    })
