"""Optimization Engine — Contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class OptimizationKind(StrEnum):
    INFRA = "INFRA"
    DATABASE = "DATABASE"
    CACHE = "CACHE"
    AI_COST = "AI_COST"
    LATENCY = "LATENCY"
    ARCHITECTURE = "ARCHITECTURE"
    COST = "COST"


@dataclass
class OptimizationStep:
    step_id: str
    title: str
    description: str
    effort: str           # LOW|MEDIUM|HIGH
    impact: str           # LOW|MEDIUM|HIGH|CRITICAL
    risk: str             # LOW|MEDIUM|HIGH
    estimated_gain: str
    rollback_procedure: str   # OBRIGATÓRIO
    validation_steps: list[str]
    advisory_only: bool = True

    def __post_init__(self) -> None:
        assert self.rollback_procedure, "rollback_procedure is required — OptimizationStep cannot be created without a rollback plan"
        assert self.advisory_only is True
        assert self.effort in ("LOW", "MEDIUM", "HIGH")
        assert self.impact in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert self.risk in ("LOW", "MEDIUM", "HIGH")


@dataclass
class OptimizationPlan:
    plan_id: str
    kind: OptimizationKind
    steps: list[OptimizationStep]
    total_estimated_gain: str
    advisory_only: bool = True
    produced_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        assert self.advisory_only is True
