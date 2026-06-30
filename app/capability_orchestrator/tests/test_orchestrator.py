"""Tests for CapabilityOrchestrator."""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from app.capability_orchestrator.contracts import (
    CapabilityKind,
    CapabilityRegistration,
    CapabilityRequest,
    CapabilityResponse,
)
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.capability_orchestrator.registry import CapabilityRegistry


def _make_registration(
    capability_id: str = "test.capability",
    kind: CapabilityKind = CapabilityKind.OBSERVATION,
) -> CapabilityRegistration:
    return CapabilityRegistration(
        capability_id=capability_id,
        kind=kind,
        name="Test Capability",
        version="1.0.0",
        description="A test capability",
        input_schema={},
        output_schema={},
        dependencies=[],
        advisory_only=True,
        owner="test-engine",
    )


def _make_request(capability_id: str = "test.capability") -> CapabilityRequest:
    return CapabilityRequest(
        request_id=str(uuid.uuid4()),
        capability_id=capability_id,
        inputs={"data": "value"},
        context={"env": "test"},
    )


def _make_response(request: CapabilityRequest) -> CapabilityResponse:
    return CapabilityResponse(
        response_id=str(uuid.uuid4()),
        request_id=request.request_id,
        capability_id=request.capability_id,
        outputs={"result": "ok"},
        evidence=["evidence-001"],
        confidence=0.9,
        advisory_only=True,
        lineage_id=str(uuid.uuid4()),
        scientific_id="sci-001",
    )


# ── Registry tests ─────────────────────────────────────────────────────────────

def test_registry_register_and_get() -> None:
    registry = CapabilityRegistry()
    reg = _make_registration()
    registry.register(reg)
    assert registry.get("test.capability") is reg


def test_registry_get_missing_returns_none() -> None:
    registry = CapabilityRegistry()
    assert registry.get("nonexistent") is None


def test_registry_list_by_kind() -> None:
    registry = CapabilityRegistry()
    registry.register(_make_registration("obs.a", CapabilityKind.OBSERVATION))
    registry.register(_make_registration("obs.b", CapabilityKind.OBSERVATION))
    registry.register(_make_registration("int.a", CapabilityKind.INTELLIGENCE))
    obs = registry.list_by_kind(CapabilityKind.OBSERVATION)
    assert len(obs) == 2
    intel = registry.list_by_kind(CapabilityKind.INTELLIGENCE)
    assert len(intel) == 1


def test_registry_all() -> None:
    registry = CapabilityRegistry()
    registry.register(_make_registration("a"))
    registry.register(_make_registration("b"))
    assert len(registry.all()) == 2


def test_registry_has() -> None:
    registry = CapabilityRegistry()
    registry.register(_make_registration("exists"))
    assert registry.has("exists") is True
    assert registry.has("nope") is False


# ── CapabilityRegistration contract tests ──────────────────────────────────────

def test_registration_advisory_only_enforced() -> None:
    with pytest.raises(AssertionError):
        CapabilityRegistration(
            capability_id="x",
            kind=CapabilityKind.OBSERVATION,
            name="X",
            version="1.0",
            description="d",
            input_schema={},
            output_schema={},
            dependencies=[],
            advisory_only=False,  # must raise
            owner="owner",
        )


def test_registration_requires_capability_id() -> None:
    with pytest.raises(AssertionError):
        CapabilityRegistration(
            capability_id="",
            kind=CapabilityKind.OBSERVATION,
            name="X",
            version="1.0",
            description="d",
            input_schema={},
            output_schema={},
            dependencies=[],
            advisory_only=True,
            owner="owner",
        )


# ── Orchestrator tests ─────────────────────────────────────────────────────────

def test_orchestrator_execute_basic() -> None:
    registry = CapabilityRegistry()
    registry.register(_make_registration())
    orch = CapabilityOrchestrator(registry)
    orch.register_handler("test.capability", _make_response)

    request = _make_request()
    response = orch.execute(request)
    assert response.advisory_only is True
    assert isinstance(response.outputs, dict)


def test_orchestrator_execute_unknown_capability_raises() -> None:
    registry = CapabilityRegistry()
    orch = CapabilityOrchestrator(registry)
    with pytest.raises(ValueError, match="not registered"):
        orch.execute(_make_request("unknown.capability"))


def test_orchestrator_execute_no_handler_raises() -> None:
    registry = CapabilityRegistry()
    registry.register(_make_registration())
    orch = CapabilityOrchestrator(registry)
    with pytest.raises(ValueError, match="No handler"):
        orch.execute(_make_request())


def test_orchestrator_discover() -> None:
    registry = CapabilityRegistry()
    registry.register(_make_registration("obs.1", CapabilityKind.OBSERVATION))
    registry.register(_make_registration("obs.2", CapabilityKind.OBSERVATION))
    registry.register(_make_registration("dev.1", CapabilityKind.DEVELOPMENT))
    orch = CapabilityOrchestrator(registry)

    obs = orch.discover(CapabilityKind.OBSERVATION)
    assert len(obs) == 2
    dev = orch.discover(CapabilityKind.DEVELOPMENT)
    assert len(dev) == 1


def test_orchestrator_registered_ids() -> None:
    registry = CapabilityRegistry()
    registry.register(_make_registration("a"))
    registry.register(_make_registration("b"))
    orch = CapabilityOrchestrator(registry)
    ids = orch.registered_ids()
    assert "a" in ids
    assert "b" in ids


def test_capability_response_advisory_only_enforced() -> None:
    with pytest.raises(AssertionError):
        CapabilityResponse(
            response_id="r",
            request_id="req",
            capability_id="cap",
            outputs={"x": 1},
            evidence=[],
            confidence=0.5,
            advisory_only=False,  # must raise
            lineage_id="lin",
            scientific_id="sci",
        )


def test_capability_response_outputs_must_be_dict() -> None:
    with pytest.raises((AssertionError, TypeError)):
        CapabilityResponse(
            response_id="r",
            request_id="req",
            capability_id="cap",
            outputs="bare string",  # type: ignore
            evidence=[],
            confidence=0.5,
            advisory_only=True,
            lineage_id="lin",
            scientific_id="sci",
        )


def test_orchestrator_isolation_engines_do_not_cross_call() -> None:
    """Engines register handlers; the orchestrator is the only caller."""
    registry = CapabilityRegistry()
    registry.register(_make_registration("engine.a"))
    registry.register(_make_registration("engine.b"))
    orch = CapabilityOrchestrator(registry)

    calls: list[str] = []

    def handler_a(req: CapabilityRequest) -> CapabilityResponse:
        calls.append("a")
        return _make_response(req)

    def handler_b(req: CapabilityRequest) -> CapabilityResponse:
        calls.append("b")
        return _make_response(req)

    orch.register_handler("engine.a", handler_a)
    orch.register_handler("engine.b", handler_b)

    orch.execute(_make_request("engine.a"))
    assert calls == ["a"]  # b was NOT called
