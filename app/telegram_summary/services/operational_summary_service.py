"""Gather operational health data for the hourly summary.

Delegates entirely to ProductionReadinessService (Operational Truth Layer)
and maps the result to OperationalSummaryPayload.  No DB queries here.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.operational_truth.production_readiness import ProductionReadinessService
from app.telegram_summary.dto import OperationalSummaryPayload
from core.config import settings

logger = logging.getLogger(__name__)


class OperationalSummaryService:
    """Evaluate all operational truth dimensions and return a summary payload."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def gather(self) -> OperationalSummaryPayload:
        """Run the full operational truth evaluation and map to payload."""
        report = ProductionReadinessService(self._db).evaluate()
        return OperationalSummaryPayload(
            status=report.status,
            operational_status=report.operational_status,
            confidence_score=report.operational_confidence_score,
            runtime_score=report.runtime_score,
            dataset_score=report.dataset_score,
            replayability_score=report.replayability_score,
            quant_reliability_score=report.quant_reliability_score,
            infra_score=report.infra_score,
            security_score=report.security_score,
            safe_mode=report.safe_mode,
            degradation_detected=report.degradation_detected,
            critical_findings=report.critical_findings,
            warnings=report.warnings,
            generated_at=report.generated_at,
            environment=settings.app_env,
        )
