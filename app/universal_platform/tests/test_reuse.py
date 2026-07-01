"""Architectural guardrails — the Universal Platform must REUSE Phase 1, not duplicate it.

The Phase 2 spec forbids re-implementing Observation, ScientificIdentity,
Evidence, Replay, Explainability, PipelineTrace, Learning Feed, Stable Hash,
Scientific Runtime or the Capability Registry. These tests assert the platform
binds to the canonical Phase 1 objects.
"""
from __future__ import annotations

from app.observation.contract import ObservationContract, stable_hash
from app.scientific_consumers.runtime import ScientificConsumerRuntime
from app.universal_platform import events, runtime
from app.universal_platform.capabilities import Phase2Platform
from app.universal_platform.runtime import UniversalObservationRuntime


def test_uses_canonical_observation_contract() -> None:
    rec = UniversalObservationRuntime().observe(
        events.UniversalEvent.create(
            project="infrastructure", domain="INFRASTRUCTURE", event_type="redis.restart",
            entity_id="r1", occurred_at="2026-06-30T10:00:00Z", severity="HIGH")
    )
    assert isinstance(rec.observation, ObservationContract)


def test_uses_canonical_scientific_runtime() -> None:
    inner = ScientificConsumerRuntime()
    r = UniversalObservationRuntime(runtime=inner)
    assert r.runtime is inner


def test_uses_canonical_stable_hash() -> None:
    # events + runtime import the canonical stable_hash, never a private copy
    assert runtime.stable_hash is stable_hash
    payload = {"b": 2, "a": 1}
    assert events.UniversalEvent.create(
        project="p", domain="D", event_type="t", entity_id="e",
        occurred_at="2026-06-30T00:00:00Z").event_id == events.stable_hash(
        {"project": "p", "domain": "D", "event_type": "t", "entity_id": "e",
         "occurred_at": "2026-06-30T00:00:00Z"})
    assert stable_hash(payload) == stable_hash({"a": 1, "b": 2})  # order-independent


def test_capability_registry_is_reused_not_reimplemented() -> None:
    from app.capability_orchestrator.registry import CapabilityRegistry
    platform = Phase2Platform()
    assert isinstance(platform.registry, CapabilityRegistry)


def test_no_engine_mutation_surface_exposed() -> None:
    """Adapters expose observe-only surfaces — no execute/mutate/decide method."""
    platform = Phase2Platform()
    for adapter in platform.adapters.values():
        public = {m for m in dir(adapter) if not m.startswith("_")}
        forbidden = {"execute", "decide", "mutate", "trade", "deploy", "heal", "write"}
        assert not (public & forbidden), f"adapter exposes forbidden surface: {public & forbidden}"
