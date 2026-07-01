"""Operational score — a deterministic projection of OperationalDiagnosis.

This is not a new diagnosis engine: it is a pure arithmetic reduction of the
incident priorities that SnapshotDiagnosisEngine.diagnose() already produces,
kept separate so the score formula can be read/audited in one place.
"""

from __future__ import annotations

from app.observer_framework.diagnosis import OperationalDiagnosis

_PRIORITY_PENALTY = {"P0": 40, "P1": 20, "P2": 10, "P3": 5}


def operational_score(diagnosis: OperationalDiagnosis) -> float:
    """100 minus a penalty per incident, floored at 0.

    P0 (critical, blocking) incidents dominate the score; P3 (informational)
    barely move it. A diagnosis with zero incidents scores 100.
    """
    penalty = sum(_PRIORITY_PENALTY.get(i.priority, 10) for i in diagnosis.incidents)
    return float(max(0, 100 - penalty))
