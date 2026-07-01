"""Executive-summary Telegram formatting for the Observer Framework cycle.

Never includes the full snapshot — only the fields the mission requires:
Operational Score, Classification, New Incidents, Resolved Incidents,
Critical Alerts, Recommendations. Reuses SnapshotDiagnosisEngine.build_recovery_plan()
for the recommendation text; formats nothing new.
"""

from __future__ import annotations

from app.observer_framework.diagnosis import (
    Certification,
    Incident,
    OperationalDiagnosis,
    SnapshotDiagnosisEngine,
    ValidationResult,
)

_MAX_RECOMMENDATIONS = 3


def format_executive_summary(
    diagnosis: OperationalDiagnosis,
    validation: ValidationResult,
    certification: Certification,
    operational_score: float,
) -> str:
    lines: list[str] = []
    lines.append("Business OS — Observer Framework")
    lines.append(f"Operational Score: {operational_score:.0f}/100")
    lines.append(f"Classification: {certification.classification}")
    lines.append(f"Overall Health: {diagnosis.overall_health} | Severity: {diagnosis.overall_severity}")

    if validation.new_incidents:
        lines.append(f"New Incidents: {len(validation.new_incidents)}")
    else:
        lines.append("New Incidents: none")

    if validation.resolved_incidents:
        lines.append(f"Resolved Incidents: {len(validation.resolved_incidents)}")
    else:
        lines.append("Resolved Incidents: none")

    critical = [i for i in diagnosis.incidents if i.priority in ("P0", "P1")]
    if critical:
        lines.append("")
        lines.append(f"Critical Alerts ({len(critical)}):")
        for inc in critical[:_MAX_RECOMMENDATIONS]:
            lines.append(f"  [{inc.priority}] {inc.source}: {inc.summary}")
    else:
        lines.append("Critical Alerts: none")

    if critical:
        lines.append("")
        lines.append("Recommendations:")
        engine = SnapshotDiagnosisEngine()
        for inc in critical[:_MAX_RECOMMENDATIONS]:
            lines.append(f"  - {_top_recommendation(engine, inc)}")

    return "\n".join(lines)


def _top_recommendation(engine: SnapshotDiagnosisEngine, incident: Incident) -> str:
    plan = engine.build_recovery_plan(incident)
    return plan.actions[0].action if plan.actions else "no recommendation available"
