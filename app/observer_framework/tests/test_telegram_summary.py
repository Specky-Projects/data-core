from __future__ import annotations

from app.observer_framework.diagnosis import (
    Certification,
    Incident,
    OperationalDiagnosis,
    ValidationResult,
)
from app.observer_framework.telegram_summary import format_executive_summary


def _incident(priority: str, source: str = "postgresql") -> Incident:
    return Incident(
        incident_id=f"inc-{source}-{priority}",
        source=source,
        domain="postgres",
        severity="critical",
        health="critical",
        summary=f"{source} is down",
        probable_cause="check connections",
        evidence=(),
        impact="domain=postgres",
        priority=priority,
    )


def _diagnosis(incidents: tuple[Incident, ...]) -> OperationalDiagnosis:
    return OperationalDiagnosis(
        snapshot_id="snap-1",
        generated_at="2026-07-01T08:00:00",
        overall_health="critical" if incidents else "healthy",
        overall_severity="critical" if incidents else "info",
        collectors_present=(),
        collectors_missing=(),
        incidents=incidents,
        integrity_verified=True,
        validation_errors=(),
    )


def test_summary_never_includes_raw_snapshot_fields() -> None:
    diagnosis = _diagnosis((_incident("P0"),))
    validation = ValidationResult("before", "after", (), (), ("inc-postgresql-P0",))
    cert = Certification("NO_GO", "1 new incident", ("before", "after"))

    text = format_executive_summary(diagnosis, validation, cert, 60.0)

    assert "records" not in text
    assert "adapter_health" not in text
    assert "integrity_hash" not in text


def test_summary_includes_required_fields() -> None:
    diagnosis = _diagnosis((_incident("P0"),))
    validation = ValidationResult("before", "after", (), (), ("inc-postgresql-P0",))
    cert = Certification("NO_GO", "1 new incident", ("before", "after"))

    text = format_executive_summary(diagnosis, validation, cert, 60.0)

    assert "Operational Score: 60" in text
    assert "Classification: NO_GO" in text
    assert "New Incidents: 1" in text
    assert "Resolved Incidents: none" in text
    assert "Critical Alerts" in text
    assert "Recommendations:" in text


def test_summary_with_no_incidents_is_short_and_clean() -> None:
    diagnosis = _diagnosis(())
    validation = ValidationResult("before", "after", (), (), ())
    cert = Certification("GO", "no incidents", ("before", "after"))

    text = format_executive_summary(diagnosis, validation, cert, 100.0)

    assert "Critical Alerts: none" in text
    assert "Recommendations:" not in text
