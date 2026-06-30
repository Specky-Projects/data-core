"""ScientificIdentityRepository — in-memory store and protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.scientific_identity.contract import (
    ScientificEntityType,
    ScientificIdentity,
    ScientificIdentityChain,
)


@runtime_checkable
class ScientificIdentityRepositoryProtocol(Protocol):
    """Port that any persistence backend must satisfy."""

    def save(self, identity: ScientificIdentity) -> None: ...

    def get(self, scientific_id: str) -> ScientificIdentity | None: ...

    def get_chain(self, lineage_id: str) -> ScientificIdentityChain: ...

    def find_by_entity(
        self,
        entity_type: ScientificEntityType,
        entity_id: str,
    ) -> ScientificIdentity | None: ...

    def all_by_lineage(self, lineage_id: str) -> list[ScientificIdentity]: ...


class InMemoryScientificIdentityRepository:
    """Reference implementation — for tests and local development only."""

    def __init__(self) -> None:
        self._by_id: dict[str, ScientificIdentity] = {}
        self._by_entity: dict[tuple[str, str], str] = {}
        self._by_lineage: dict[str, list[str]] = {}

    def save(self, identity: ScientificIdentity) -> None:
        sid = identity.scientific_id
        self._by_id[sid] = identity
        self._by_entity[(str(identity.entity_type), identity.entity_id)] = sid
        self._by_lineage.setdefault(identity.lineage_id, []).append(sid)

    def get(self, scientific_id: str) -> ScientificIdentity | None:
        return self._by_id.get(scientific_id)

    def get_chain(self, lineage_id: str) -> ScientificIdentityChain:
        ids = self._by_lineage.get(lineage_id, [])
        entries = tuple(self._by_id[sid] for sid in ids if sid in self._by_id)
        return ScientificIdentityChain(lineage_id=lineage_id, entries=entries)

    def find_by_entity(
        self,
        entity_type: ScientificEntityType,
        entity_id: str,
    ) -> ScientificIdentity | None:
        sid = self._by_entity.get((str(entity_type), entity_id))
        return self._by_id.get(sid) if sid else None

    def all_by_lineage(self, lineage_id: str) -> list[ScientificIdentity]:
        ids = self._by_lineage.get(lineage_id, [])
        return [self._by_id[sid] for sid in ids if sid in self._by_id]
