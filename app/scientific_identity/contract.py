"""ScientificIdentity — Canonical Contract.

Immutable, deterministic, replayable identity for every scientific entity.
Produced once; never mutated; stable across replays.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


SCIENTIFIC_IDENTITY_VERSION = "scientific-identity-v1"


# ── Utilities ─────────────────────────────────────────────────────────────────


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _normalize(value[k]) for k in sorted(value)}
    if isinstance(value, list | tuple):
        return [_normalize(item) for item in value]
    return value


def stable_json(value: Any) -> str:
    return json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_hash(value: Any, length: int = 32) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:length]


# ── Entity type taxonomy ───────────────────────────────────────────────────────


class ScientificEntityType(str, Enum):
    """All entities that can carry a ScientificIdentity."""

    OBSERVATION = "OBSERVATION"
    CONTEXT = "CONTEXT"
    EVIDENCE = "EVIDENCE"
    CLAIM = "CLAIM"
    DECISION = "DECISION"
    COMMITTEE = "COMMITTEE"
    PREVIEW = "PREVIEW"
    EXECUTION = "EXECUTION"
    OUTCOME = "OUTCOME"
    REPLAY = "REPLAY"
    LEARNING = "LEARNING"
    EXPERIMENT = "EXPERIMENT"
    KNOWLEDGE = "KNOWLEDGE"


# ── Contract ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ScientificIdentity:
    """Universal scientific identity.

    The ``scientific_id`` is the canonical handle. It is deterministic:
    identical inputs always produce the same ID, making it safe to
    reconstruct identities during replay without an external registry.
    """

    entity_type: ScientificEntityType
    entity_id: str
    lineage_id: str
    producer: str
    produced_at: str
    schema_version: str = SCIENTIFIC_IDENTITY_VERSION
    parent_scientific_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def scientific_id(self) -> str:
        """Deterministic ID — stable across replays."""
        return stable_hash(
            {
                "entity_type": str(self.entity_type),
                "entity_id": self.entity_id,
                "lineage_id": self.lineage_id,
                "producer": self.producer,
                "schema_version": self.schema_version,
            }
        )

    @property
    def identity_hash(self) -> str:
        """Full-payload hash including metadata."""
        return stable_hash(asdict(self))

    def as_payload(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.entity_id.strip():
            errors.append("entity_id must not be empty")
        if not self.lineage_id.strip():
            errors.append("lineage_id must not be empty")
        if not self.producer.strip():
            errors.append("producer must not be empty")
        if not self.produced_at.strip():
            errors.append("produced_at must not be empty")
        return errors


# ── Chain snapshot ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ScientificIdentityChain:
    """Ordered chain of scientific identities for a single lineage.

    Represents the full lifecycle of one scientific decision from the
    first observation to the final knowledge entry. Immutable — additions
    produce a new chain.
    """

    lineage_id: str
    entries: tuple[ScientificIdentity, ...] = ()

    def append(self, identity: ScientificIdentity) -> ScientificIdentityChain:
        if identity.lineage_id != self.lineage_id:
            raise ValueError(
                f"identity lineage_id {identity.lineage_id!r} "
                f"does not match chain lineage_id {self.lineage_id!r}"
            )
        return ScientificIdentityChain(
            lineage_id=self.lineage_id,
            entries=(*self.entries, identity),
        )

    @property
    def chain_hash(self) -> str:
        return stable_hash([e.scientific_id for e in self.entries])

    def entity_types(self) -> list[ScientificEntityType]:
        return [e.entity_type for e in self.entries]

    def latest(self) -> ScientificIdentity | None:
        return self.entries[-1] if self.entries else None
