"""Base protocol for development capabilities."""
from __future__ import annotations

from typing import Any, Protocol


class DevelopmentCapability(Protocol):
    name: str

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]: ...
