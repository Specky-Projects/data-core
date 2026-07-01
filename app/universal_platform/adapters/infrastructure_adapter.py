"""WS2 — Infrastructure Adapter.

Turns infrastructure telemetry (Docker, Coolify, PostgreSQL, Redis, workers,
scheduler, CPU, RAM, disk, network, logs, health, ready, deploy, backup) into
scientific observations with a derived severity. It observes only — it never
restarts, scales, deploys or heals anything.
"""
from __future__ import annotations

from typing import Any

from app.universal_platform.adapters.base import BaseAdapter
from app.universal_platform.events import Severity, UniversalEvent, coerce_severity

# Component → default severity when an event does not carry one explicitly.
_COMPONENT_DEFAULT_SEVERITY = {
    "docker": Severity.MEDIUM,
    "coolify": Severity.MEDIUM,
    "postgres": Severity.HIGH,
    "redis": Severity.HIGH,
    "worker": Severity.MEDIUM,
    "scheduler": Severity.HIGH,
    "cpu": Severity.LOW,
    "ram": Severity.LOW,
    "disk": Severity.MEDIUM,
    "network": Severity.MEDIUM,
    "logs": Severity.INFO,
    "health": Severity.HIGH,
    "ready": Severity.HIGH,
    "deploy": Severity.MEDIUM,
    "backup": Severity.MEDIUM,
}

# Event-type keywords that escalate severity regardless of component default.
_ESCALATION_KEYWORDS = {
    "restart": Severity.HIGH,
    "crash": Severity.CRITICAL,
    "down": Severity.CRITICAL,
    "failure": Severity.CRITICAL,
    "failed": Severity.HIGH,
    "unhealthy": Severity.HIGH,
    "not_ready": Severity.HIGH,
    "timeout": Severity.HIGH,
    "oom": Severity.CRITICAL,
    "degraded": Severity.MEDIUM,
    "recovered": Severity.INFO,
}


def _derive_severity(component: str, event_type: str, explicit: Any) -> Severity:
    if explicit is not None:
        return coerce_severity(explicit)
    et = event_type.lower()
    escalated = Severity.INFO
    for keyword, sev in _ESCALATION_KEYWORDS.items():
        if keyword in et and sev.rank > escalated.rank:
            escalated = sev
    base = _COMPONENT_DEFAULT_SEVERITY.get(component.lower(), Severity.INFO)
    return escalated if escalated.rank > base.rank else base


class InfrastructureAdapter(BaseAdapter):
    PROJECT = "infrastructure"
    DOMAIN = "INFRASTRUCTURE"

    def to_event(self, raw: dict[str, Any]) -> UniversalEvent:
        component = str(raw.get("component") or "unknown")
        event_type = str(raw.get("event_type") or f"{component}.event")
        entity_id = str(raw.get("service") or raw.get("entity_id") or component)
        occurred_at = str(raw.get("occurred_at") or raw.get("observed_at") or "")
        severity = _derive_severity(component, event_type, raw.get("severity"))
        metrics = dict(raw.get("metrics") or {})
        for key in ("cpu", "ram", "disk", "network", "uptime_s", "restarts", "health", "ready"):
            if key in raw:
                metrics.setdefault(key, raw[key])
        confidence = 1.0  # infra telemetry is a directly observed fact
        return UniversalEvent.create(
            project=self.PROJECT,
            domain=self.DOMAIN,
            event_type=event_type,
            entity_id=entity_id,
            occurred_at=occurred_at,
            confidence=confidence,
            severity=severity,
            evidence=raw.get("evidence", ()),
            metrics=metrics,
            payload=dict(raw),
            metadata={"component": component},
        )
