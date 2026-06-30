"""Business OS 5.0 — UEL health and observability."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.universal_execution_log.models import UELDashboardReport, UEL_VERSION


@dataclass
class UELHealthReport:
    healthy: bool
    ledger_version: str = UEL_VERSION
    table_reachable: bool = False
    total_executions: int = 0
    active_executions: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    avg_duration_ms: float = 0.0
    evidence_attached: int = 0
    learnings_attached: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def status(self) -> str:
        if self.errors:
            return "UNHEALTHY"
        if self.warnings:
            return "DEGRADED"
        return "HEALTHY"


def compute_uel_health(dashboard: UELDashboardReport | None, table_reachable: bool) -> UELHealthReport:
    """Derive UEL health from dashboard report."""
    if not table_reachable:
        return UELHealthReport(
            healthy=False,
            table_reachable=False,
            errors=["universal_executions table is not reachable"],
        )

    if dashboard is None:
        return UELHealthReport(
            healthy=False,
            table_reachable=True,
            errors=["dashboard query returned None"],
        )

    warnings: list[str] = []
    errors: list[str] = []

    if dashboard.failure_rate > 0.5:
        errors.append(f"High failure rate: {dashboard.failure_rate:.1%}")
    elif dashboard.failure_rate > 0.2:
        warnings.append(f"Elevated failure rate: {dashboard.failure_rate:.1%}")

    if dashboard.rollback_rate > 0.3:
        warnings.append(f"Elevated rollback rate: {dashboard.rollback_rate:.1%}")

    active = dashboard.by_status.get("running", 0) + dashboard.by_status.get("planned", 0)

    return UELHealthReport(
        healthy=len(errors) == 0,
        table_reachable=True,
        total_executions=dashboard.total,
        active_executions=active,
        success_rate=dashboard.success_rate,
        failure_rate=dashboard.failure_rate,
        avg_duration_ms=dashboard.avg_duration_ms,
        evidence_attached=dashboard.total_evidence_attached,
        learnings_attached=dashboard.total_learnings_attached,
        warnings=warnings,
        errors=errors,
    )
