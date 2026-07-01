"""WS7 — Unified Alert Engine.

A single engine replaces per-project alerts. It evaluates a batch of
``UniversalObservationRecord`` and emits ``UnifiedAlert`` objects that always
carry Severity, Evidence, Root Cause, Confidence, Recommended Action and a
Replay reference — never a bare message. It also *correlates* records across
projects so that, e.g., a Redis restart + a scheduler failure + a Mirror desync
collapse into one Critical Infrastructure Alert.

Advisory + shadow only: publishing does not transmit anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from app.scientific_identity.contract import stable_hash
from app.universal_platform.events import Severity
from app.universal_platform.runtime import UniversalObservationRecord

# Records at or above this severity raise a standalone alert if uncorrelated.
SINGLETON_ALERT_THRESHOLD = Severity.HIGH


@dataclass(frozen=True)
class CorrelationRule:
    """Fires when every required (project, event-substring) signal is present."""

    rule_id: str
    title: str
    required: tuple[tuple[str, str], ...]   # (project, event_type_substring)
    severity: Severity
    root_cause: str
    recommended_action: str

    def matches(self, index: dict[str, list[UniversalObservationRecord]]) -> list[UniversalObservationRecord] | None:
        hits: list[UniversalObservationRecord] = []
        for project, needle in self.required:
            found = next(
                (
                    r
                    for r in index.get(project, [])
                    if needle in r.event.event_type
                ),
                None,
            )
            if found is None:
                return None
            hits.append(found)
        return hits


DEFAULT_CORRELATION_RULES: tuple[CorrelationRule, ...] = (
    CorrelationRule(
        rule_id="critical-infrastructure",
        title="Critical Infrastructure Alert",
        required=(
            ("infrastructure", "redis"),
            ("infrastructure", "scheduler"),
            ("mirror", "desync"),
        ),
        severity=Severity.CRITICAL,
        root_cause="Cache/scheduler instability propagated into Mirror synchronisation loss.",
        recommended_action="Stabilise Redis + scheduler, then re-validate Mirror sync before any real action.",
    ),
    CorrelationRule(
        rule_id="scientific-regression",
        title="Scientific Regression Alert",
        required=(
            ("research", "regression"),
            ("mirror", "degradation"),
        ),
        severity=Severity.HIGH,
        root_cause="Research detected a regression coincident with a Mirror performance drop.",
        recommended_action="Freeze learning feed promotion and open a scientific regression review.",
    ),
)


@dataclass(frozen=True)
class UnifiedAlert:
    alert_id: str
    title: str
    severity: Severity
    evidence: tuple[str, ...]
    root_cause: str
    confidence: float
    recommended_action: str
    replay_ref: str
    correlated_event_ids: tuple[str, ...]
    created_at: str
    rule_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "title": self.title,
            "severity": self.severity.value,
            "evidence": list(self.evidence),
            "root_cause": self.root_cause,
            "confidence": self.confidence,
            "recommended_action": self.recommended_action,
            "replay_ref": self.replay_ref,
            "correlated_event_ids": list(self.correlated_event_ids),
            "created_at": self.created_at,
            "rule_id": self.rule_id,
        }


def _evidence_refs(records: Iterable[UniversalObservationRecord]) -> tuple[str, ...]:
    refs: list[str] = []
    for r in records:
        refs.append(f"observation:{r.observation.observation_id}")
        refs.append(f"lineage:{r.lineage_id}")
    return tuple(dict.fromkeys(refs))  # stable dedupe


class UnifiedAlertEngine:
    ADVISORY_ONLY = True
    SHADOW_MODE = True

    def __init__(self, rules: tuple[CorrelationRule, ...] | None = None) -> None:
        self.rules = rules if rules is not None else DEFAULT_CORRELATION_RULES

    def evaluate(self, records: list[UniversalObservationRecord]) -> list[UnifiedAlert]:
        index: dict[str, list[UniversalObservationRecord]] = {}
        for r in records:
            index.setdefault(r.event.project, []).append(r)

        alerts: list[UnifiedAlert] = []
        consumed: set[str] = set()

        # 1) correlated alerts take priority
        for rule in self.rules:
            hits = rule.matches(index)
            if hits is None:
                continue
            for h in hits:
                consumed.add(h.event.event_id)
            confidence = round(sum(h.event.confidence for h in hits) / len(hits), 4)
            alerts.append(
                UnifiedAlert(
                    alert_id=stable_hash({"rule": rule.rule_id, "events": sorted(h.event.event_id for h in hits)}),
                    title=rule.title,
                    severity=rule.severity,
                    evidence=_evidence_refs(hits),
                    root_cause=rule.root_cause,
                    confidence=confidence,
                    recommended_action=rule.recommended_action,
                    replay_ref=hits[0].pipeline_id,
                    correlated_event_ids=tuple(sorted(h.event.event_id for h in hits)),
                    created_at=hits[0].event.occurred_at,
                    rule_id=rule.rule_id,
                )
            )

        # 2) standalone alerts for high/critical records not already correlated
        for r in records:
            if r.event.event_id in consumed:
                continue
            if r.severity.rank < SINGLETON_ALERT_THRESHOLD.rank:
                continue
            alerts.append(
                UnifiedAlert(
                    alert_id=stable_hash({"single": r.event.event_id}),
                    title=f"{r.event.project}: {r.event.event_type}",
                    severity=r.severity,
                    evidence=_evidence_refs([r]),
                    root_cause=f"{r.event.event_type} observed on {r.event.entity_id}.",
                    confidence=r.event.confidence,
                    recommended_action="Review the observed component and validate in runtime before acting.",
                    replay_ref=r.pipeline_id,
                    correlated_event_ids=(r.event.event_id,),
                    created_at=r.event.occurred_at,
                )
            )

        alerts.sort(key=lambda a: (-a.severity.rank, a.title))
        return alerts

    def publish(self, alert: UnifiedAlert) -> dict[str, Any]:
        """Advisory publish — records intent, transmits nothing (shadow mode)."""
        return {
            "alert_id": alert.alert_id,
            "severity": alert.severity.value,
            "published": False,
            "shadow_mode": True,
            "advisory_only": True,
            "payload": alert.as_dict(),
        }
