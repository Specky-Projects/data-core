"""Business OS 5.0 — UEL adapter base and project adapters.

Each project inherits UELAdapter and calls emit_execution() instead of creating
their own log model. The adapter translates project-specific context into the
canonical EmitExecutionRequest, then delegates to the UELRepository.

This file ships with concrete adapters for the known projects. Future projects
subclass UELAdapter and override _build_request().
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.universal_execution_log.models import (
    AttachRequest,
    CompleteExecutionRequest,
    EmitExecutionRequest,
    ExecutionSurface,
    ExecutionType,
    FailExecutionRequest,
    ProjectId,
    RollbackExecutionRequest,
    UELDecision,
    UELMetrics,
    UELOutcome,
    UniversalExecution,
)
from app.universal_execution_log.repository import UELRepository


class UELAdapter:
    """Base adapter. Projects subclass this and call the public API."""

    project_id: str = ProjectId.UNKNOWN
    default_surface: ExecutionSurface = ExecutionSurface.UNKNOWN
    default_type: ExecutionType = ExecutionType.UNKNOWN
    default_actor: str = "system"

    def __init__(self, repository: UELRepository | None = None) -> None:
        self._repo = repository if repository is not None else UELRepository()

    # ── Public project-facing API ──────────────────────────────────────────────

    def emit(
        self,
        capability_id: str,
        *,
        actor: str | None = None,
        executor: str = "",
        mission_id: str = "",
        correlation_id: str = "",
        parent_execution_id: str = "",
        execution_plan_id: str = "",
        decision: UELDecision | None = None,
        surface: ExecutionSurface | None = None,
        execution_type: ExecutionType | None = None,
        tags: dict[str, str] | None = None,
        timestamp: datetime | None = None,
    ) -> UniversalExecution:
        req = EmitExecutionRequest(
            project_id=self.project_id,
            capability_id=capability_id,
            execution_surface=surface or self.default_surface,
            execution_type=execution_type or self.default_type,
            actor=actor or self.default_actor,
            executor=executor,
            mission_id=mission_id,
            correlation_id=correlation_id,
            parent_execution_id=parent_execution_id,
            execution_plan_id=execution_plan_id,
            decision=decision or UELDecision(),
            tags=tags or {},
            timestamp=timestamp or datetime.now(timezone.utc),
        )
        return self._repo.emit_execution(req)

    def complete(
        self,
        execution_id: str,
        *,
        summary: str = "",
        value_delivered: bool = True,
        artifacts: list[str] | None = None,
        payload: dict[str, Any] | None = None,
        latency_ms: float = 0.0,
        items_processed: int = 0,
        finished_at: datetime | None = None,
    ) -> UniversalExecution:
        outcome = UELOutcome(
            summary=summary,
            value_delivered=value_delivered,
            artifacts=artifacts or [],
            payload=payload or {},
        )
        metrics = UELMetrics(
            latency_ms=latency_ms,
            items_processed=items_processed,
        )
        return self._repo.complete_execution(
            CompleteExecutionRequest(
                execution_id=execution_id,
                outcome=outcome,
                metrics=metrics,
                finished_at=finished_at or datetime.now(timezone.utc),
            )
        )

    def fail(
        self,
        execution_id: str,
        error: str,
        *,
        errors: list[str] | None = None,
        finished_at: datetime | None = None,
    ) -> UniversalExecution:
        return self._repo.fail_execution(
            FailExecutionRequest(
                execution_id=execution_id,
                error=error,
                errors=errors or [],
                finished_at=finished_at or datetime.now(timezone.utc),
            )
        )

    def rollback(
        self,
        execution_id: str,
        reason: str,
        *,
        target_id: str = "",
        finished_at: datetime | None = None,
    ) -> UniversalExecution:
        return self._repo.rollback_execution(
            RollbackExecutionRequest(
                execution_id=execution_id,
                rollback_reason=reason,
                rollback_target_id=target_id,
                finished_at=finished_at or datetime.now(timezone.utc),
            )
        )

    def attach_evidence(self, execution_id: str, ids: list[str]) -> UniversalExecution:
        return self._repo.attach_evidence(AttachRequest(execution_id=execution_id, ids=ids))

    def attach_knowledge(self, execution_id: str, ids: list[str]) -> UniversalExecution:
        return self._repo.attach_knowledge(AttachRequest(execution_id=execution_id, ids=ids))

    def attach_learning(self, execution_id: str, ids: list[str]) -> UniversalExecution:
        return self._repo.attach_learning(AttachRequest(execution_id=execution_id, ids=ids))

    @property
    def repository(self) -> UELRepository:
        return self._repo


# ── Project adapters ──────────────────────────────────────────────────────────


class CryptoUELAdapter(UELAdapter):
    """Adapter for Poupi Crypto (trading signals, mirror executions)."""

    project_id = ProjectId.POUPI_CRYPTO
    default_surface = ExecutionSurface.TRADING
    default_type = ExecutionType.SIGNAL
    default_actor = "crypto-engine"

    def emit_signal(
        self,
        capability_id: str,
        *,
        signal_id: str = "",
        actor: str = "crypto-engine",
        mission_id: str = "",
        **kwargs: Any,
    ) -> UniversalExecution:
        tags = {"signal_id": signal_id} if signal_id else {}
        return self.emit(
            capability_id,
            actor=actor,
            mission_id=mission_id,
            execution_type=ExecutionType.SIGNAL,
            tags=tags,
            **kwargs,
        )

    def emit_trade(
        self,
        capability_id: str,
        *,
        trade_id: str = "",
        actor: str = "executor",
        **kwargs: Any,
    ) -> UniversalExecution:
        tags = {"trade_id": trade_id} if trade_id else {}
        return self.emit(
            capability_id,
            actor=actor,
            execution_type=ExecutionType.TRADE,
            tags=tags,
            **kwargs,
        )


class BabyUELAdapter(UELAdapter):
    """Adapter for Poupi Baby (product discovery, alerts, deals)."""

    project_id = ProjectId.POUPI_BABY
    default_surface = ExecutionSurface.ANALYTICS
    default_type = ExecutionType.DISCOVERY
    default_actor = "baby-engine"

    def emit_discovery(
        self,
        capability_id: str,
        *,
        product_id: str = "",
        actor: str = "discovery-engine",
        **kwargs: Any,
    ) -> UniversalExecution:
        tags = {"product_id": product_id} if product_id else {}
        return self.emit(
            capability_id,
            actor=actor,
            execution_type=ExecutionType.DISCOVERY,
            tags=tags,
            **kwargs,
        )

    def emit_alert(
        self,
        capability_id: str,
        *,
        alert_id: str = "",
        actor: str = "alert-engine",
        **kwargs: Any,
    ) -> UniversalExecution:
        tags = {"alert_id": alert_id} if alert_id else {}
        return self.emit(
            capability_id,
            actor=actor,
            execution_type=ExecutionType.ALERT,
            surface=ExecutionSurface.WORKFLOW,
            tags=tags,
            **kwargs,
        )


class SinaloUELAdapter(UELAdapter):
    """Adapter for Sinalo (SEO, content, affiliate, social)."""

    project_id = ProjectId.SINALO
    default_surface = ExecutionSurface.SEO
    default_type = ExecutionType.PUBLISH
    default_actor = "sinalo-engine"

    def emit_content(
        self,
        capability_id: str,
        *,
        content_id: str = "",
        actor: str = "content-engine",
        **kwargs: Any,
    ) -> UniversalExecution:
        tags = {"content_id": content_id} if content_id else {}
        return self.emit(
            capability_id,
            actor=actor,
            execution_type=ExecutionType.PUBLISH,
            surface=ExecutionSurface.CONTENT,
            tags=tags,
            **kwargs,
        )

    def emit_seo(
        self,
        capability_id: str,
        *,
        page_id: str = "",
        actor: str = "seo-engine",
        **kwargs: Any,
    ) -> UniversalExecution:
        tags = {"page_id": page_id} if page_id else {}
        return self.emit(
            capability_id,
            actor=actor,
            execution_type=ExecutionType.ANALYZE,
            surface=ExecutionSurface.SEO,
            tags=tags,
            **kwargs,
        )


class BusinessOSUELAdapter(UELAdapter):
    """Adapter for internal Business OS decisions and orchestrations."""

    project_id = ProjectId.BUSINESS_OS
    default_surface = ExecutionSurface.AUTONOMOUS_DECISION
    default_type = ExecutionType.ORCHESTRATE
    default_actor = "business-os"
