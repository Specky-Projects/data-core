"""SnapshotDiagnosisEngine — the entirety of Claude Code's operational role
under the Observer Framework architecture.

Everything here is a pure function of a RuntimeSnapshotContract (or a pair of
them, for validation). Nothing connects to production. Nothing executes a
fix — RecoveryPlan is a list of recommendations, never an action.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.observation_engine.contracts import ObservationHealth, ObservationSeverity
from app.observer_framework.snapshot_contract import (
    ObservationRecordSnapshot,
    RuntimeSnapshotContract,
    health_rank,
    severity_rank,
)
from app.scientific_identity.contract import stable_hash

# ── Collector domain map (per COLLECTOR_SPECIFICATION.md) ────────────────────
# Maps a requested observation domain to the adapter `source` value(s) that
# currently (even partially) satisfy it. An empty tuple means "no collector
# exists yet — PENDING Observer Framework build-out".

EXPECTED_COLLECTOR_DOMAINS: tuple[str, ...] = (
    "mirror", "specky", "cav", "committee", "executor", "exchange",
    "research", "universal_platform", "scheduler", "workers",
    "postgres", "redis", "docker", "coolify", "vps",
)

DOMAIN_TO_SOURCE: dict[str, tuple[str, ...]] = {
    "mirror": ("mirror-strategy",),
    "specky": ("mirror-strategy:specky",),
    "cav": ("mirror-strategy:cav",),
    "committee": (),
    "executor": (),
    "exchange": ("binance",),
    "research": ("research-engine",),
    "universal_platform": ("universal-platform",),
    "scheduler": ("apscheduler",),
    "workers": (),
    "postgres": ("postgresql",),
    "redis": ("redis",),
    "docker": ("docker-engine",),
    "coolify": (),
    "vps": ("vps",),
}

# Any record whose severity or health is worse than these thresholds is an incident.
_INCIDENT_SEVERITY_THRESHOLD = severity_rank(ObservationSeverity.WARNING)
_INCIDENT_HEALTH_THRESHOLD = health_rank(ObservationHealth.DEGRADED)


@dataclass(frozen=True)
class Incident:
    incident_id: str
    source: str
    domain: str
    severity: str
    health: str
    summary: str
    probable_cause: str
    evidence: tuple[str, ...]
    impact: str
    priority: str  # P0-P3

    def as_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "source": self.source,
            "domain": self.domain,
            "severity": self.severity,
            "health": self.health,
            "summary": self.summary,
            "probable_cause": self.probable_cause,
            "evidence": list(self.evidence),
            "impact": self.impact,
            "priority": self.priority,
        }


@dataclass(frozen=True)
class OperationalDiagnosis:
    snapshot_id: str
    generated_at: str
    overall_health: str
    overall_severity: str
    collectors_present: tuple[str, ...]
    collectors_missing: tuple[str, ...]
    incidents: tuple[Incident, ...]
    integrity_verified: bool
    validation_errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "generated_at": self.generated_at,
            "overall_health": self.overall_health,
            "overall_severity": self.overall_severity,
            "collectors_present": list(self.collectors_present),
            "collectors_missing": list(self.collectors_missing),
            "incidents": [i.as_dict() for i in self.incidents],
            "integrity_verified": self.integrity_verified,
            "validation_errors": list(self.validation_errors),
        }


@dataclass(frozen=True)
class RecoveryAction:
    order: int
    action: str
    risk: str
    validation_criteria: str


@dataclass(frozen=True)
class RecoveryPlan:
    incident_id: str
    actions: tuple[RecoveryAction, ...]
    executes_changes: bool = False  # always False — recommendations only

    def as_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "executes_changes": self.executes_changes,
            "actions": [
                {"order": a.order, "action": a.action, "risk": a.risk, "validation_criteria": a.validation_criteria}
                for a in self.actions
            ],
        }


@dataclass(frozen=True)
class ValidationResult:
    before_snapshot_id: str
    after_snapshot_id: str
    resolved_incidents: tuple[str, ...]
    unresolved_incidents: tuple[str, ...]
    new_incidents: tuple[str, ...]

    @property
    def fully_resolved(self) -> bool:
        return not self.unresolved_incidents and not self.new_incidents

    def as_dict(self) -> dict[str, Any]:
        return {
            "before_snapshot_id": self.before_snapshot_id,
            "after_snapshot_id": self.after_snapshot_id,
            "resolved_incidents": list(self.resolved_incidents),
            "unresolved_incidents": list(self.unresolved_incidents),
            "new_incidents": list(self.new_incidents),
            "fully_resolved": self.fully_resolved,
        }


@dataclass(frozen=True)
class Certification:
    classification: str  # GO | GO_WITH_OBSERVATIONS | NO_GO
    justification: str
    evidence_snapshot_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "justification": self.justification,
            "evidence_snapshot_ids": list(self.evidence_snapshot_ids),
        }


_PROBABLE_CAUSE_HINTS: dict[str, str] = {
    "postgresql": "check active_connections / db_size_mb trend for saturation or bloat",
    "redis": "check used_memory_mb / hit_rate for eviction pressure or cache-miss storm",
    "docker-engine": "check containers_stopped for a crashed/restarting container",
    "apscheduler": "check jobs_failed_24h for a stuck or erroring job",
    "vps": "check cpu_pct/mem_pct/disk_pct for resource exhaustion",
    "mirror-strategy": "check dd_pct (drawdown) and active_trades for risk-engine intervention",
    "binance": "check open_orders/positions for a stuck order or exchange desync",
    "universal-platform": "check initialized flag — platform likely failed fail-safe startup",
    "telegram-bot": "check errors_24h for delivery failures",
    "business-os-platform": "check capabilities_registered for a missing/failed engine registration",
}


def _probable_cause(record: ObservationRecordSnapshot) -> str:
    if record.source in _PROBABLE_CAUSE_HINTS:
        return _PROBABLE_CAUSE_HINTS[record.source]
    base_source = record.source.split(":")[0]
    if base_source in _PROBABLE_CAUSE_HINTS:
        return _PROBABLE_CAUSE_HINTS[base_source]
    return f"no heuristic for source '{record.source}' — inspect evidence/metrics directly"


def _priority_for(severity: ObservationSeverity, health: ObservationHealth) -> str:
    rank = max(severity_rank(severity), health_rank(health))
    return {0: "P3", 1: "P2", 2: "P1", 3: "P0"}.get(rank, "P2")


class SnapshotDiagnosisEngine:
    """Pure, deterministic — never touches production."""

    def diagnose(self, snapshot: RuntimeSnapshotContract) -> OperationalDiagnosis:
        validation_errors = tuple(snapshot.validate())
        integrity_ok = snapshot.verify_integrity()

        incidents: list[Incident] = []
        for r in snapshot.records:
            sev = ObservationSeverity(r.severity)
            health = ObservationHealth(r.health)
            if severity_rank(sev) < _INCIDENT_SEVERITY_THRESHOLD and health_rank(health) < _INCIDENT_HEALTH_THRESHOLD:
                continue
            incidents.append(
                Incident(
                    incident_id=stable_hash({"observation_id": r.observation_id, "kind": "incident"}),
                    source=r.source,
                    domain=r.domain,
                    severity=r.severity,
                    health=r.health,
                    summary=f"{r.source} reported severity={r.severity} health={r.health}",
                    probable_cause=_probable_cause(r),
                    evidence=(f"observation:{r.observation_id}", f"scientific_id:{r.scientific_id}", *r.evidence),
                    impact=f"domain={r.domain}, project={r.project}",
                    priority=_priority_for(sev, health),
                )
            )
        incidents.sort(key=lambda i: {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(i.priority, 2))

        present = snapshot.collectors_present()
        collectors_present = tuple(
            d for d in EXPECTED_COLLECTOR_DOMAINS if any(s in present for s in DOMAIN_TO_SOURCE.get(d, ()))
        )
        collectors_missing = tuple(d for d in EXPECTED_COLLECTOR_DOMAINS if d not in collectors_present)

        worst_sev = snapshot.worst_severity()
        worst_health = snapshot.worst_health()

        return OperationalDiagnosis(
            snapshot_id=snapshot.snapshot_id,
            generated_at=snapshot.captured_at,
            overall_health=(worst_health.value if worst_health else ObservationHealth.UNKNOWN.value),
            overall_severity=(worst_sev.value if worst_sev else ObservationSeverity.INFO.value),
            collectors_present=collectors_present,
            collectors_missing=collectors_missing,
            incidents=tuple(incidents),
            integrity_verified=integrity_ok,
            validation_errors=validation_errors,
        )

    def build_recovery_plan(self, incident: Incident) -> RecoveryPlan:
        """Recommendations only. `executes_changes` is always False."""
        actions = (
            RecoveryAction(
                order=1,
                action=f"Reproduce: re-collect a fresh snapshot from '{incident.source}' and confirm the condition persists.",
                risk="none — read-only",
                validation_criteria="new snapshot shows the same severity/health for this source",
            ),
            RecoveryAction(
                order=2,
                action=f"Root cause: {incident.probable_cause}",
                risk="none — diagnostic only",
                validation_criteria="root cause confirmed against raw evidence, not just the hint",
            ),
            RecoveryAction(
                order=3,
                action=(
                    "Recommend fix to the Business OS Recovery Engine (out of band). "
                    "Claude Code does not execute this step."
                ),
                risk="depends on the fix — assessed by the Recovery Engine operator",
                validation_criteria="operator confirms fix applied",
            ),
            RecoveryAction(
                order=4,
                action="Request a validation snapshot after the fix and re-run diagnose()/compare().",
                risk="none — read-only",
                validation_criteria="incident no longer appears in the after-snapshot's diagnosis",
            ),
        )
        return RecoveryPlan(incident_id=incident.incident_id, actions=actions, executes_changes=False)

    def compare(self, before: RuntimeSnapshotContract, after: RuntimeSnapshotContract) -> ValidationResult:
        before_diag = self.diagnose(before)
        after_diag = self.diagnose(after)
        before_ids = {(i.source, i.domain): i.incident_id for i in before_diag.incidents}
        after_ids = {(i.source, i.domain): i.incident_id for i in after_diag.incidents}

        resolved = tuple(v for k, v in before_ids.items() if k not in after_ids)
        unresolved = tuple(v for k, v in before_ids.items() if k in after_ids)
        new = tuple(v for k, v in after_ids.items() if k not in before_ids)

        return ValidationResult(
            before_snapshot_id=before.snapshot_id,
            after_snapshot_id=after.snapshot_id,
            resolved_incidents=resolved,
            unresolved_incidents=unresolved,
            new_incidents=new,
        )

    def certify(self, validation: ValidationResult) -> Certification:
        if validation.new_incidents:
            return Certification(
                classification="NO_GO",
                justification=f"{len(validation.new_incidents)} new incident(s) appeared after the fix.",
                evidence_snapshot_ids=(validation.before_snapshot_id, validation.after_snapshot_id),
            )
        if validation.unresolved_incidents:
            return Certification(
                classification="GO_WITH_OBSERVATIONS",
                justification=f"{len(validation.unresolved_incidents)} incident(s) persist after the fix.",
                evidence_snapshot_ids=(validation.before_snapshot_id, validation.after_snapshot_id),
            )
        return Certification(
            classification="GO",
            justification="All previously observed incidents resolved; no new incidents introduced.",
            evidence_snapshot_ids=(validation.before_snapshot_id, validation.after_snapshot_id),
        )
