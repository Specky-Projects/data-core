"""Capability Orchestrator — Contracts.

All engines register capabilities here. Engines never call each other directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable


CAPABILITY_ORCHESTRATOR_VERSION = "capability-orchestrator-v1"


class CapabilityKind(str, Enum):
    OBSERVATION = "observation"
    INTELLIGENCE = "intelligence"
    DEVELOPMENT = "development"
    RESEARCH = "research"
    OPTIMIZATION = "optimization"
    KNOWLEDGE = "knowledge"
    DECISION = "decision"


@dataclass(frozen=True)
class CapabilityRegistration:
    capability_id: str
    kind: CapabilityKind
    name: str
    version: str
    description: str
    input_schema: dict
    output_schema: dict
    dependencies: list[str]
    advisory_only: bool
    owner: str
    registered_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        assert self.capability_id, "capability_id is required"
        assert self.name, "name is required"
        assert self.owner, "owner is required"
        assert self.advisory_only is True, "All capabilities must be advisory_only=True"


@dataclass(frozen=True)
class CapabilityRequest:
    request_id: str
    capability_id: str
    inputs: dict[str, Any]
    context: dict[str, Any]
    requested_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CapabilityResponse:
    response_id: str
    request_id: str
    capability_id: str
    outputs: dict[str, Any]
    evidence: list[str]
    confidence: float
    advisory_only: bool
    lineage_id: str
    scientific_id: str
    responded_at: datetime = field(default_factory=datetime.utcnow)
    error: str | None = None

    def __post_init__(self) -> None:
        assert self.advisory_only is True, "CapabilityResponse must always be advisory_only=True"
        assert isinstance(self.outputs, dict), "outputs must be a dict — never a bare string"
