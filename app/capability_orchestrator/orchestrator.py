"""Capability Orchestrator — central routing hub.

Engines never call each other directly. All inter-engine communication
goes through CapabilityOrchestrator.
"""
from __future__ import annotations

from typing import Callable

from app.capability_orchestrator.contracts import (
    CapabilityKind,
    CapabilityRegistration,
    CapabilityRequest,
    CapabilityResponse,
)
from app.capability_orchestrator.registry import CapabilityRegistry


class CapabilityOrchestrator:
    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry
        self._handlers: dict[str, Callable[[CapabilityRequest], CapabilityResponse]] = {}

    def register_handler(
        self,
        capability_id: str,
        handler: Callable[[CapabilityRequest], CapabilityResponse],
    ) -> None:
        self._handlers[capability_id] = handler

    def execute(self, request: CapabilityRequest) -> CapabilityResponse:
        cap = self.registry.get(request.capability_id)
        if cap is None:
            raise ValueError(f"Capability '{request.capability_id}' not registered")
        handler = self._handlers.get(request.capability_id)
        if handler is None:
            raise ValueError(f"No handler registered for capability '{request.capability_id}'")
        response = handler(request)
        assert response.advisory_only is True, "Handler returned non-advisory response"
        return response

    def discover(self, kind: CapabilityKind) -> list[CapabilityRegistration]:
        return self.registry.list_by_kind(kind)

    def registered_ids(self) -> list[str]:
        return [c.capability_id for c in self.registry.all()]
