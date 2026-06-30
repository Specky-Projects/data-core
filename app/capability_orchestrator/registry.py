"""Capability Registry — stores registered capabilities."""
from __future__ import annotations

from app.capability_orchestrator.contracts import CapabilityKind, CapabilityRegistration


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityRegistration] = {}

    def register(self, cap: CapabilityRegistration) -> None:
        self._capabilities[cap.capability_id] = cap

    def get(self, capability_id: str) -> CapabilityRegistration | None:
        return self._capabilities.get(capability_id)

    def list_by_kind(self, kind: CapabilityKind) -> list[CapabilityRegistration]:
        return [c for c in self._capabilities.values() if c.kind == kind]

    def all(self) -> list[CapabilityRegistration]:
        return list(self._capabilities.values())

    def has(self, capability_id: str) -> bool:
        return capability_id in self._capabilities
