from __future__ import annotations

from app.observer_framework.diagnosis import Incident, OperationalDiagnosis
from app.observer_framework.scoring import operational_score


def _diagnosis(priorities: list[str]) -> OperationalDiagnosis:
    incidents = tuple(
        Incident(
            incident_id=f"inc-{i}",
            source="postgresql",
            domain="postgres",
            severity="warning",
            health="degraded",
            summary="s",
            probable_cause="c",
            evidence=(),
            impact="i",
            priority=p,
        )
        for i, p in enumerate(priorities)
    )
    return OperationalDiagnosis(
        snapshot_id="snap-1",
        generated_at="2026-07-01T00:00:00",
        overall_health="degraded",
        overall_severity="warning",
        collectors_present=(),
        collectors_missing=(),
        incidents=incidents,
        integrity_verified=True,
        validation_errors=(),
    )


def test_no_incidents_scores_100() -> None:
    assert operational_score(_diagnosis([])) == 100.0


def test_p0_incident_penalizes_40() -> None:
    assert operational_score(_diagnosis(["P0"])) == 60.0


def test_multiple_incidents_stack_penalties() -> None:
    assert operational_score(_diagnosis(["P0", "P1", "P3"])) == 100 - 40 - 20 - 5


def test_score_never_goes_below_zero() -> None:
    assert operational_score(_diagnosis(["P0"] * 10)) == 0.0
