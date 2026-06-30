"""ScientificIdentityBuilder — constructs identities deterministically."""

from __future__ import annotations

from datetime import datetime, timezone

from app.scientific_identity.contract import (
    SCIENTIFIC_IDENTITY_VERSION,
    ScientificEntityType,
    ScientificIdentity,
    ScientificIdentityChain,
    stable_hash,
)


class ScientificIdentityBuilder:
    """Fluent builder for ScientificIdentity.

    Produces identities that are deterministic and replayable.
    The ``lineage_id`` must be provided once and shared across all entities
    in the same decision lifecycle.
    """

    def __init__(self, lineage_id: str, producer: str) -> None:
        self._lineage_id = lineage_id
        self._producer = producer
        self._parent: str | None = None
        self._metadata: dict = {}

    def with_parent(self, parent_scientific_id: str) -> ScientificIdentityBuilder:
        self._parent = parent_scientific_id
        return self

    def with_metadata(self, metadata: dict) -> ScientificIdentityBuilder:
        self._metadata = metadata
        return self

    def build(
        self,
        entity_type: ScientificEntityType,
        entity_id: str,
        produced_at: datetime | str | None = None,
    ) -> ScientificIdentity:
        if produced_at is None:
            produced_at = datetime.now(tz=timezone.utc)
        if isinstance(produced_at, datetime):
            produced_at = produced_at.isoformat()

        identity = ScientificIdentity(
            entity_type=entity_type,
            entity_id=entity_id,
            lineage_id=self._lineage_id,
            producer=self._producer,
            produced_at=produced_at,
            schema_version=SCIENTIFIC_IDENTITY_VERSION,
            parent_scientific_id=self._parent,
            metadata=self._metadata,
        )
        self._parent = identity.scientific_id
        return identity

    def build_chain(
        self,
        entity_type: ScientificEntityType,
        entity_id: str,
        chain: ScientificIdentityChain,
        produced_at: datetime | str | None = None,
    ) -> tuple[ScientificIdentity, ScientificIdentityChain]:
        identity = self.build(entity_type, entity_id, produced_at)
        return identity, chain.append(identity)

    @staticmethod
    def derive_lineage_id(*parts: str) -> str:
        """Deterministic lineage ID from any set of stable string parts."""
        return stable_hash(list(parts), length=24)

    @staticmethod
    def new_chain(lineage_id: str) -> ScientificIdentityChain:
        return ScientificIdentityChain(lineage_id=lineage_id)
