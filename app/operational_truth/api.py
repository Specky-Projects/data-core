"""Operational Truth Layer — FastAPI router.

Endpoints
─────────
GET /health/operational   Full production readiness report
GET /health/readiness     Same as /health/operational (alias)
GET /health/runtime       Runtime truth only (fast)
GET /health/datasets      Dataset truth only
GET /health/replayability Replayability truth only
GET /health/quant         Quant reliability truth only
GET /health/confidence    Operational confidence score (ultra-fast summary)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.operational_truth.analyzers.dataset import analyze_dataset
from app.operational_truth.analyzers.infra import analyze_infra
from app.operational_truth.analyzers.quant import analyze_quant
from app.operational_truth.analyzers.replayability import analyze_replayability
from app.operational_truth.analyzers.runtime import analyze_runtime
from app.operational_truth.production_readiness import ProductionReadinessService
from app.operational_truth.safety import evaluate_safety
from database.session import get_db

router = APIRouter(tags=["operational-truth"])

_STATUS_HTTP: dict[str, int] = {
    "OK": 200,
    "WARNING": 200,
    "CRITICAL": 503,
}

_OP_STATUS_HTTP: dict[str, int] = {
    "HEALTHY": 200,
    "DEGRADED": 200,
    "PARTIALLY_UNSAFE": 200,
    "UNSAFE": 503,
    "CRITICAL": 503,
}


def _report_to_dict(report: Any) -> dict:
    return report.model_dump(mode="json")


@router.get("/health/operational", summary="Full operational truth report")
def health_operational(db: Session = Depends(get_db)) -> JSONResponse:
    report = ProductionReadinessService(db).evaluate()
    safety = evaluate_safety(
        type("C", (), {
            "operational_confidence_score": report.operational_confidence_score,
            "safe_mode": report.safe_mode,
            "infra_score": report.infra_score,
        })()
    )
    payload = _report_to_dict(report)
    payload["safety"] = {
        "fail_closed": safety.fail_closed,
        "kill_switch": safety.kill_switch,
        "pressure_protection": safety.pressure_protection,
        "severity": safety.severity,
        "reason": safety.reason,
    }
    return JSONResponse(payload, status_code=_STATUS_HTTP.get(report.status, 200))


@router.get("/health/readiness", summary="Production readiness (alias for /health/operational)")
def health_readiness(db: Session = Depends(get_db)) -> JSONResponse:
    return health_operational(db)


@router.get("/health/runtime", summary="Runtime truth: scheduler + worker + queue")
def health_runtime(db: Session = Depends(get_db)) -> JSONResponse:
    infra = analyze_infra(db)
    runtime = analyze_runtime(db)
    status_code = _OP_STATUS_HTTP.get(runtime.status, 200)
    return JSONResponse(runtime.model_dump(mode="json"), status_code=status_code)


@router.get("/health/datasets", summary="Dataset truth: freshness + lag + integrity")
def health_datasets(db: Session = Depends(get_db)) -> JSONResponse:
    datasets = analyze_dataset(db)
    status_code = _OP_STATUS_HTTP.get(datasets.status, 200)
    return JSONResponse(datasets.model_dump(mode="json"), status_code=status_code)


@router.get("/health/replayability", summary="Replayability: gaps + determinism + reconstruction")
def health_replayability() -> JSONResponse:
    replay = analyze_replayability()
    status_code = _OP_STATUS_HTTP.get(replay.status, 200)
    return JSONResponse(replay.model_dump(mode="json"), status_code=status_code)


@router.get("/health/quant", summary="Quant reliability: signals + calibration + entropy")
def health_quant() -> JSONResponse:
    quant = analyze_quant()
    status_code = _OP_STATUS_HTTP.get(quant.status, 200)
    return JSONResponse(quant.model_dump(mode="json"), status_code=status_code)


@router.get("/health/confidence", summary="Operational confidence score (fast summary)")
def health_confidence(db: Session = Depends(get_db)) -> JSONResponse:
    report = ProductionReadinessService(db).evaluate()
    return JSONResponse(
        {
            "operational_confidence_score": report.operational_confidence_score,
            "status": report.status,
            "operational_status": report.operational_status,
            "degradation_detected": report.degradation_detected,
            "safe_mode": report.safe_mode,
            "critical_findings_count": len(report.critical_findings),
            "warnings_count": len(report.warnings),
            "generated_at": report.generated_at.isoformat(),
            "environment": report.environment,
        },
        status_code=_STATUS_HTTP.get(report.status, 200),
    )
