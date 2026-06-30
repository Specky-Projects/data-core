"""ObservationContract — first link in the scientific chain.

An Observation represents a fact observed from the world.
It must NOT contain:
- opinion
- decision
- score
- risk
- prediction

It is immutable, deterministic, and replayable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


OBSERVATION_VERSION = "observation-v1"


# ── Utilities (self-contained — no cross-module imports) ──────────────────────


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


# ── Observation type taxonomy ─────────────────────────────────────────────────


class ObservationType(str, Enum):
    """All fact types the platform can observe."""

    SIGNAL = "SIGNAL"
    FUNDING = "FUNDING"
    OPEN_INTEREST = "OPEN_INTEREST"
    PRICE = "PRICE"
    VOLUME = "VOLUME"
    SENTIMENT = "SENTIMENT"
    ON_CHAIN = "ON_CHAIN"
    MACRO = "MACRO"
    ORDER_BOOK = "ORDER_BOOK"
    TRADE_FLOW = "TRADE_FLOW"
    LIQUIDITY = "LIQUIDITY"
    KNOWLEDGE_SOURCE = "KNOWLEDGE_SOURCE"
    GENERIC = "GENERIC"


class ObservationQuality(str, Enum):
    CERTIFIED = "CERTIFIED"
    VERIFIED = "VERIFIED"
    RAW = "RAW"
    UNVERIFIED = "UNVERIFIED"


# ── Contract ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ObservationContract:
    """Canonical observation — pure facts, no inference.

    ``observation_id`` is assigned by the producer.
    ``payload_hash`` is computed from ``payload`` deterministically
    so replays can verify fidelity of the original fact.
    """

    observation_id: str
    producer: str
    observed_at: str
    observation_type: ObservationType
    payload: dict[str, Any]
    payload_hash: str
    quality: ObservationQuality = ObservationQuality.RAW
    symbol: str | None = None
    scientific_identity_id: str | None = None
    schema_version: str = OBSERVATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        observation_id: str,
        producer: str,
        observed_at: str,
        observation_type: ObservationType,
        payload: dict[str, Any],
        quality: ObservationQuality = ObservationQuality.RAW,
        symbol: str | None = None,
        scientific_identity_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ObservationContract:
        """Factory — computes payload_hash automatically."""
        return cls(
            observation_id=observation_id,
            producer=producer,
            observed_at=observed_at,
            observation_type=observation_type,
            payload=payload,
            payload_hash=stable_hash(payload),
            quality=quality,
            symbol=symbol,
            scientific_identity_id=scientific_identity_id,
            schema_version=OBSERVATION_VERSION,
            metadata=metadata or {},
        )

    def verify_payload_integrity(self) -> bool:
        return self.payload_hash == stable_hash(self.payload)

    def as_payload(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.observation_id.strip():
            errors.append("observation_id must not be empty")
        if not self.producer.strip():
            errors.append("producer must not be empty")
        if not self.observed_at.strip():
            errors.append("observed_at must not be empty")
        if not self.payload:
            errors.append("payload must not be empty — observations must contain facts")
        if not self.verify_payload_integrity():
            errors.append("payload_hash does not match payload — integrity violation")
        return errors


# ── Snapshot ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ObservationSnapshot:
    """Point-in-time immutable snapshot of an ObservationContract.

    Used to freeze the observation state at the moment it enters the
    scientific chain, enabling deterministic replay.
    """

    snapshot_id: str
    observation_id: str
    captured_at: str
    observation_hash: str
    payload_hash: str
    producer: str
    schema_version: str = OBSERVATION_VERSION

    @classmethod
    def from_observation(
        cls,
        observation: ObservationContract,
        captured_at: str,
    ) -> ObservationSnapshot:
        return cls(
            snapshot_id=stable_hash(
                {"observation_id": observation.observation_id, "captured_at": captured_at}
            ),
            observation_id=observation.observation_id,
            captured_at=captured_at,
            observation_hash=stable_hash(observation.as_payload()),
            payload_hash=observation.payload_hash,
            producer=observation.producer,
        )

    def verify(self, observation: ObservationContract) -> bool:
        return stable_hash(observation.as_payload()) == self.observation_hash
