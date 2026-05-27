"""ProductionReadinessService — main entry point for the Operational Truth Layer."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.operational_truth.analyzers.dataset import analyze_dataset
from app.operational_truth.analyzers.infra import analyze_infra
from app.operational_truth.analyzers.quant import analyze_quant
from app.operational_truth.analyzers.replayability import analyze_replayability
from app.operational_truth.analyzers.runtime import analyze_runtime
from app.operational_truth.analyzers.security import analyze_security
from app.operational_truth.dto import ProductionReadinessReport, readiness_from_status
from app.operational_truth.engine import compute_confidence
from core.config import settings

logger = logging.getLogger(__name__)


class ProductionReadinessService:
    """Evaluate all operational truth dimensions and return a consolidated report."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def evaluate(self) -> ProductionReadinessReport:
        t0 = time.perf_counter()
        now = datetime.now(timezone.utc)

        try:
            from app.operational_truth import metrics as _m
            with _m.evaluation_duration_seconds.time():
                return self._run(now)
        except Exception:
            return self._run(now)
        finally:
            elapsed = time.perf_counter() - t0
            logger.debug("operational_truth: evaluation completed in %.3fs", elapsed)

    def _run(self, now: datetime) -> ProductionReadinessReport:
        db = self._db

        infra = analyze_infra(db)
        runtime = analyze_runtime(db)
        datasets = analyze_dataset(db)
        replayability = analyze_replayability()
        quant = analyze_quant()
        security = analyze_security()

        confidence = compute_confidence(runtime, datasets, replayability, quant, infra, security)

        report = ProductionReadinessReport(
            status=readiness_from_status(confidence.status),
            operational_confidence_score=confidence.operational_confidence_score,
            operational_status=confidence.status,
            runtime_score=confidence.runtime_score,
            dataset_score=confidence.dataset_score,
            replayability_score=confidence.replayability_score,
            quant_reliability_score=confidence.quant_reliability_score,
            infra_score=confidence.infra_score,
            security_score=confidence.security_score,
            degradation_detected=confidence.degradation_detected,
            safe_mode=confidence.safe_mode,
            critical_findings=confidence.critical_findings,
            warnings=confidence.warnings,
            recommendations=confidence.recommendations,
            runtime=runtime,
            datasets=datasets,
            replayability=replayability,
            quant=quant,
            infra=infra,
            security=security,
            generated_at=now,
            environment=settings.app_env,
        )

        # Publish Prometheus metrics (best-effort — never fail the request)
        try:
            from app.operational_truth.metrics import publish_report
            publish_report(report)
        except Exception as exc:
            logger.warning("operational_truth: metrics publish failed: %s", exc)

        return report
