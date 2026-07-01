"""Capability Registry — Phase 2.

Registers the universal-platform capabilities and wires their handlers through
the *existing* CapabilityOrchestrator. No project ever reaches an adapter or
runtime directly — everything is routed by the orchestrator, and every response
is advisory_only.

Capabilities registered:
    poupi.observe        infra.observe        telegram.observe
    affiliate.observe    runtime.observe      runtime.coverage
    runtime.snapshot     daily_brief.generate alert.evaluate
    alert.publish
"""
from __future__ import annotations

import uuid
from typing import Any, Callable

from app.capability_orchestrator.contracts import (
    CapabilityKind,
    CapabilityRegistration,
    CapabilityRequest,
    CapabilityResponse,
)
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.capability_orchestrator.registry import CapabilityRegistry
from app.scientific_identity.contract import stable_hash
from app.universal_platform import UNIVERSAL_PLATFORM_VERSION
from app.universal_platform.adapters import (
    AffiliateAdapter,
    InfrastructureAdapter,
    PoupiBabyAdapter,
    TelegramAdapter,
)
from app.universal_platform.alert_engine import UnifiedAlertEngine
from app.universal_platform.daily_brief import DailyBriefBuilder
from app.universal_platform.events import UniversalEvent, coerce_severity
from app.universal_platform.runtime import UniversalObservationRuntime

PHASE2_CAPABILITY_IDS = (
    "poupi.observe",
    "infra.observe",
    "telegram.observe",
    "affiliate.observe",
    "runtime.observe",
    "runtime.coverage",
    "runtime.snapshot",
    "daily_brief.generate",
    "alert.evaluate",
    "alert.publish",
)


def _registration(
    capability_id: str, kind: CapabilityKind, name: str, description: str
) -> CapabilityRegistration:
    return CapabilityRegistration(
        capability_id=capability_id,
        kind=kind,
        name=name,
        version=UNIVERSAL_PLATFORM_VERSION,
        description=description,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        dependencies=[],
        advisory_only=True,
        owner="universal-platform",
    )


def _event_from_inputs(inputs: dict[str, Any]) -> UniversalEvent:
    """Build a UniversalEvent from a raw capability input payload."""
    ev = dict(inputs.get("event") or inputs)
    return UniversalEvent.create(
        project=str(ev.get("project") or "unknown"),
        domain=str(ev.get("domain") or "GENERIC"),
        event_type=str(ev.get("event_type") or "generic.event"),
        entity_id=str(ev.get("entity_id") or ev.get("candidate_id") or "UNKNOWN"),
        occurred_at=str(ev.get("occurred_at") or ""),
        confidence=ev.get("confidence", 1.0),
        severity=coerce_severity(ev.get("severity")),
        evidence=ev.get("evidence", ()),
        metrics=ev.get("metrics") or {},
        payload=ev.get("payload") or ev,
        outcome=ev.get("outcome"),
    )


class Phase2Platform:
    """Top-level Phase 2 wiring: adapters + runtime + brief + alerts via orchestrator."""

    def __init__(self) -> None:
        self.registry = CapabilityRegistry()
        self.orchestrator = CapabilityOrchestrator(self.registry)
        self.runtime = UniversalObservationRuntime()
        self.adapters = {
            "poupi-baby": PoupiBabyAdapter(self.runtime),
            "infrastructure": InfrastructureAdapter(self.runtime),
            "telegram": TelegramAdapter(self.runtime),
            "affiliate": AffiliateAdapter(self.runtime),
        }
        self.alert_engine = UnifiedAlertEngine()
        self.brief_builder = DailyBriefBuilder()
        self._register_all()

    # ── registration ─────────────────────────────────────────────────────────
    def _register_all(self) -> None:
        specs: list[tuple[str, CapabilityKind, str, str, Callable]] = [
            ("poupi.observe", CapabilityKind.OBSERVATION, "Poupi Baby Observe",
             "Observe a Poupi Baby lifecycle event.", self._h_adapter("poupi-baby")),
            ("infra.observe", CapabilityKind.OBSERVATION, "Infrastructure Observe",
             "Observe an infrastructure telemetry event.", self._h_adapter("infrastructure")),
            ("telegram.observe", CapabilityKind.OBSERVATION, "Telegram Observe",
             "Observe an inbound Telegram message.", self._h_adapter("telegram")),
            ("affiliate.observe", CapabilityKind.OBSERVATION, "Affiliate Observe",
             "Observe an affiliate monetisation event.", self._h_adapter("affiliate")),
            ("runtime.observe", CapabilityKind.OBSERVATION, "Runtime Observe",
             "Materialise any UniversalEvent into the scientific chain.", self._h_runtime_observe),
            ("runtime.coverage", CapabilityKind.OBSERVATION, "Runtime Coverage",
             "Return coverage metrics for an event.", self._h_runtime_coverage),
            ("runtime.snapshot", CapabilityKind.OBSERVATION, "Runtime Snapshot",
             "Return an audit snapshot for an event.", self._h_runtime_snapshot),
            ("daily_brief.generate", CapabilityKind.KNOWLEDGE, "Daily Brief Generate",
             "Generate the unified daily brief.", self._h_daily_brief),
            ("alert.evaluate", CapabilityKind.DECISION, "Alert Evaluate",
             "Evaluate and correlate alerts.", self._h_alert_evaluate),
            ("alert.publish", CapabilityKind.DECISION, "Alert Publish",
             "Advisory (shadow) publish of an alert.", self._h_alert_publish),
        ]
        for cap_id, kind, name, desc, handler in specs:
            self.registry.register(_registration(cap_id, kind, name, desc))
            self.orchestrator.register_handler(cap_id, handler)

    # ── handlers ──────────────────────────────────────────────────────────────
    def _response(
        self, req: CapabilityRequest, outputs: dict[str, Any], *,
        evidence: list[str], confidence: float, lineage_id: str, scientific_id: str,
    ) -> CapabilityResponse:
        return CapabilityResponse(
            response_id=str(uuid.uuid4()),
            request_id=req.request_id,
            capability_id=req.capability_id,
            outputs=outputs,
            evidence=evidence,
            confidence=confidence,
            advisory_only=True,
            lineage_id=lineage_id,
            scientific_id=scientific_id,
        )

    def _h_adapter(self, project: str) -> Callable[[CapabilityRequest], CapabilityResponse]:
        adapter = self.adapters[project]

        def handler(req: CapabilityRequest) -> CapabilityResponse:
            raw = dict(req.inputs.get("event") or req.inputs)
            record = adapter.observe(raw)
            return self._response(
                req, record.as_dict(),
                evidence=[f"observation:{record.observation.observation_id}"],
                confidence=record.event.confidence,
                lineage_id=record.lineage_id,
                scientific_id=record.observation.observation_id,
            )

        return handler

    def _h_runtime_observe(self, req: CapabilityRequest) -> CapabilityResponse:
        record = self.runtime.observe(_event_from_inputs(req.inputs))
        return self._response(
            req, record.as_dict(),
            evidence=[f"observation:{record.observation.observation_id}"],
            confidence=record.event.confidence,
            lineage_id=record.lineage_id,
            scientific_id=record.observation.observation_id,
        )

    def _h_runtime_coverage(self, req: CapabilityRequest) -> CapabilityResponse:
        record = self.runtime.observe(_event_from_inputs(req.inputs))
        return self._response(
            req, {"coverage": record.coverage.as_dict()},
            evidence=[f"observation:{record.observation.observation_id}"],
            confidence=record.coverage.coverage_ratio,
            lineage_id=record.lineage_id,
            scientific_id=record.observation.observation_id,
        )

    def _h_runtime_snapshot(self, req: CapabilityRequest) -> CapabilityResponse:
        record = self.runtime.observe(_event_from_inputs(req.inputs))
        return self._response(
            req, {"audit": record.audit.as_dict()},
            evidence=[f"snapshot:{record.audit.snapshot_id}"],
            confidence=record.coverage.coverage_ratio,
            lineage_id=record.lineage_id,
            scientific_id=record.audit.snapshot_id,
        )

    def _records_from_events(self, events: list[dict[str, Any]]):
        records = []
        for raw in events:
            project = str(raw.get("project") or "")
            adapter = self.adapters.get(project)
            if adapter is not None:
                records.append(adapter.observe(raw))
            else:
                records.append(self.runtime.observe(_event_from_inputs({"event": raw})))
        return records

    def _h_daily_brief(self, req: CapabilityRequest) -> CapabilityResponse:
        events = list(req.inputs.get("events") or [])
        generated_at = str(req.inputs.get("generated_at") or "")
        records = self._records_from_events(events)
        alerts = self.alert_engine.evaluate(records)
        brief = self.brief_builder.build(records, alerts=alerts, generated_at=generated_at)
        return self._response(
            req, brief.as_dict(),
            evidence=[f"records:{len(records)}", f"alerts:{len(alerts)}"],
            confidence=brief.scientific_health,
            lineage_id=brief.brief_id,
            scientific_id=brief.brief_id,
        )

    def _h_alert_evaluate(self, req: CapabilityRequest) -> CapabilityResponse:
        events = list(req.inputs.get("events") or [])
        records = self._records_from_events(events)
        alerts = self.alert_engine.evaluate(records)
        return self._response(
            req, {"alerts": [a.as_dict() for a in alerts], "count": len(alerts)},
            evidence=[f"records:{len(records)}"],
            confidence=1.0,
            lineage_id=stable_hash({"alerts": [a.alert_id for a in alerts]}),
            scientific_id=stable_hash({"eval": len(alerts)}),
        )

    def _h_alert_publish(self, req: CapabilityRequest) -> CapabilityResponse:
        alert = dict(req.inputs.get("alert") or {})
        envelope = {
            "alert_id": alert.get("alert_id", ""),
            "severity": alert.get("severity", "INFO"),
            "published": False,
            "shadow_mode": True,
            "advisory_only": True,
            "payload": alert,
        }
        return self._response(
            req, envelope,
            evidence=[f"alert:{alert.get('alert_id', '')}"],
            confidence=1.0,
            lineage_id=str(alert.get("alert_id", "")),
            scientific_id=str(alert.get("replay_ref", "")),
        )

    # ── convenience ────────────────────────────────────────────────────────────
    def execute(self, capability_id: str, inputs: dict[str, Any]) -> CapabilityResponse:
        request = CapabilityRequest(
            request_id=str(uuid.uuid4()),
            capability_id=capability_id,
            inputs=inputs,
            context={"platform": UNIVERSAL_PLATFORM_VERSION},
        )
        return self.orchestrator.execute(request)

    def status(self) -> dict[str, Any]:
        return {
            "version": UNIVERSAL_PLATFORM_VERSION,
            "capabilities": self.orchestrator.registered_ids(),
            "adapters": {p: a.descriptor() for p, a in self.adapters.items()},
            "advisory_only": True,
            "shadow_mode": True,
            "read_only": True,
        }
