"""Base protocol for optimizers."""
from __future__ import annotations

from typing import Any, Protocol

from app.optimization_engine.contracts import OptimizationStep


class Optimizer(Protocol):
    name: str

    def suggest(self, inputs: dict[str, Any]) -> list[OptimizationStep]: ...
