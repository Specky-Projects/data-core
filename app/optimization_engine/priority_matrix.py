"""PriorityMatrix — scores and sorts OptimizationSteps."""
from __future__ import annotations

from app.optimization_engine.contracts import OptimizationStep


class PriorityMatrix:
    IMPACT = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    EFFORT = {"LOW": 4, "MEDIUM": 2, "HIGH": 1}   # inverted — low effort = higher score
    RISK = {"LOW": 1.0, "MEDIUM": 0.7, "HIGH": 0.4}

    def score(self, step: OptimizationStep) -> float:
        return (
            self.IMPACT.get(step.impact, 1)
            * self.EFFORT.get(step.effort, 1)
            * self.RISK.get(step.risk, 1.0)
        )

    def prioritize(self, steps: list[OptimizationStep]) -> list[OptimizationStep]:
        return sorted(steps, key=self.score, reverse=True)
