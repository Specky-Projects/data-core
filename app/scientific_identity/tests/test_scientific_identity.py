"""Tests for ScientificIdentity — Phase 2.2."""

from app.scientific_identity.adapter import (
    from_business_os_claim,
    from_event,
)
from app.scientific_identity.builder import ScientificIdentityBuilder
from app.scientific_identity.contract import (
    SCIENTIFIC_IDENTITY_VERSION,
    ScientificEntityType,
    ScientificIdentity,
    ScientificIdentityChain,
)
from app.scientific_identity.repository import InMemoryScientificIdentityRepository
from app.scientific_identity.validator import ScientificIdentityValidator


# ── Contract ───────────────────────────────────────────────────────────────────


def test_scientific_id_is_deterministic() -> None:
    identity = ScientificIdentity(
        entity_type=ScientificEntityType.OBSERVATION,
        entity_id="obs-001",
        lineage_id="lineage-abc",
        producer="sip/strategy-a",
        produced_at="2026-06-30T12:00:00+00:00",
    )
    assert identity.scientific_id == identity.scientific_id
    assert len(identity.scientific_id) == 32


def test_same_inputs_produce_same_scientific_id() -> None:
    kwargs = dict(
        entity_type=ScientificEntityType.EVIDENCE,
        entity_id="ev-999",
        lineage_id="lineage-xyz",
        producer="data-core/knowledge",
        produced_at="2026-06-30T00:00:00+00:00",
    )
    a = ScientificIdentity(**kwargs)
    b = ScientificIdentity(**kwargs)
    assert a.scientific_id == b.scientific_id


def test_different_entity_type_produces_different_id() -> None:
    base = dict(
        entity_id="id-1",
        lineage_id="lineage-1",
        producer="p",
        produced_at="2026-01-01T00:00:00+00:00",
    )
    obs = ScientificIdentity(entity_type=ScientificEntityType.OBSERVATION, **base)
    ev = ScientificIdentity(entity_type=ScientificEntityType.EVIDENCE, **base)
    assert obs.scientific_id != ev.scientific_id


def test_schema_version_default() -> None:
    identity = ScientificIdentity(
        entity_type=ScientificEntityType.DECISION,
        entity_id="d-1",
        lineage_id="l-1",
        producer="sip",
        produced_at="2026-01-01T00:00:00",
    )
    assert identity.schema_version == SCIENTIFIC_IDENTITY_VERSION


def test_validate_rejects_empty_fields() -> None:
    identity = ScientificIdentity(
        entity_type=ScientificEntityType.OUTCOME,
        entity_id="",
        lineage_id="",
        producer="",
        produced_at="",
    )
    errors = identity.validate()
    assert len(errors) >= 3


# ── Builder ────────────────────────────────────────────────────────────────────


def test_builder_sets_parent_automatically() -> None:
    builder = ScientificIdentityBuilder("lineage-1", "sip/test")
    obs = builder.build(ScientificEntityType.OBSERVATION, "obs-1", "2026-06-30T00:00:00")
    ev = builder.build(ScientificEntityType.EVIDENCE, "ev-1", "2026-06-30T00:01:00")
    assert ev.parent_scientific_id == obs.scientific_id


def test_builder_derive_lineage_is_deterministic() -> None:
    lid_a = ScientificIdentityBuilder.derive_lineage_id("strategy-A", "BTCUSDT", "2026-06-30")
    lid_b = ScientificIdentityBuilder.derive_lineage_id("strategy-A", "BTCUSDT", "2026-06-30")
    assert lid_a == lid_b
    assert len(lid_a) == 24


def test_builder_chain() -> None:
    builder = ScientificIdentityBuilder("lineage-x", "sip")
    chain = ScientificIdentityBuilder.new_chain("lineage-x")
    obs, chain = builder.build_chain(ScientificEntityType.OBSERVATION, "obs-1", chain)
    ev, chain = builder.build_chain(ScientificEntityType.EVIDENCE, "ev-1", chain)
    assert chain.entity_types() == [ScientificEntityType.OBSERVATION, ScientificEntityType.EVIDENCE]
    assert chain.latest() == ev


# ── Chain ──────────────────────────────────────────────────────────────────────


def test_chain_append_rejects_mismatched_lineage() -> None:
    chain = ScientificIdentityChain(lineage_id="lineage-A")
    identity = ScientificIdentity(
        entity_type=ScientificEntityType.EVIDENCE,
        entity_id="ev-1",
        lineage_id="lineage-B",
        producer="p",
        produced_at="2026-01-01T00:00:00",
    )
    try:
        chain.append(identity)
        assert False, "should have raised"
    except ValueError:
        pass


def test_chain_hash_changes_when_entry_added() -> None:
    builder = ScientificIdentityBuilder("lin-1", "sip")
    chain = ScientificIdentityBuilder.new_chain("lin-1")
    h0 = chain.chain_hash
    obs, chain = builder.build_chain(ScientificEntityType.OBSERVATION, "obs-1", chain)
    assert chain.chain_hash != h0


# ── Repository ─────────────────────────────────────────────────────────────────


def test_repository_save_and_get() -> None:
    repo = InMemoryScientificIdentityRepository()
    identity = ScientificIdentity(
        entity_type=ScientificEntityType.KNOWLEDGE,
        entity_id="k-1",
        lineage_id="lin-1",
        producer="kg",
        produced_at="2026-06-30T00:00:00",
    )
    repo.save(identity)
    retrieved = repo.get(identity.scientific_id)
    assert retrieved == identity


def test_repository_get_chain_preserves_order() -> None:
    repo = InMemoryScientificIdentityRepository()
    builder = ScientificIdentityBuilder("lin-2", "sip")
    chain = ScientificIdentityBuilder.new_chain("lin-2")
    for etype, eid in [
        (ScientificEntityType.OBSERVATION, "obs-1"),
        (ScientificEntityType.EVIDENCE, "ev-1"),
        (ScientificEntityType.DECISION, "d-1"),
    ]:
        identity, chain = builder.build_chain(etype, eid, chain, "2026-01-01T00:00:00")
        repo.save(identity)

    retrieved_chain = repo.get_chain("lin-2")
    assert len(retrieved_chain.entries) == 3


def test_repository_find_by_entity() -> None:
    repo = InMemoryScientificIdentityRepository()
    identity = ScientificIdentity(
        entity_type=ScientificEntityType.REPLAY,
        entity_id="replay-42",
        lineage_id="lin-3",
        producer="sip/replay",
        produced_at="2026-06-30T00:00:00",
    )
    repo.save(identity)
    found = repo.find_by_entity(ScientificEntityType.REPLAY, "replay-42")
    assert found == identity


# ── Validator ──────────────────────────────────────────────────────────────────


def test_validator_accepts_valid_identity() -> None:
    validator = ScientificIdentityValidator()
    identity = ScientificIdentity(
        entity_type=ScientificEntityType.CLAIM,
        entity_id="claim-1",
        lineage_id="lin-ok",
        producer="business-os",
        produced_at="2026-06-30T00:00:00",
        metadata={"capability_id": "cap-A"},
    )
    result = validator.validate_identity(identity)
    assert result.valid
    assert result.errors() == []


def test_validator_warns_chain_not_starting_with_observation() -> None:
    validator = ScientificIdentityValidator()
    builder = ScientificIdentityBuilder("lin-warn", "sip")
    chain = ScientificIdentityBuilder.new_chain("lin-warn")
    _, chain = builder.build_chain(ScientificEntityType.EVIDENCE, "ev-1", chain, "2026-01-01T00:00:00")
    result = validator.validate_chain(chain)
    codes = [f.code for f in result.findings]
    assert "CHAIN_MUST_START_WITH_OBSERVATION" in codes


# ── Adapters ───────────────────────────────────────────────────────────────────


def test_from_event_adapter() -> None:
    identity = from_event(
        entity_type=ScientificEntityType.EXECUTION,
        entity_id="exec-1",
        lineage_id="lin-exec",
        producer="execution_runtime",
    )
    assert identity.entity_type == ScientificEntityType.EXECUTION
    assert identity.scientific_id  # non-empty


def test_from_business_os_claim_adapter() -> None:
    identity = from_business_os_claim("claim-99", "cap-A", "lin-bos")
    assert identity.entity_type == ScientificEntityType.CLAIM
    assert identity.producer == "business-os/foundation/cap-A"
