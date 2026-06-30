"""ObservationRepository — in-memory store and protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.observation.contract import ObservationContract, ObservationType


@runtime_checkable
class ObservationRepositoryProtocol(Protocol):
    """Port that any persistence backend must satisfy."""

    def save(self, observation: ObservationContract) -> None: ...

    def get(self, observation_id: str) -> ObservationContract | None: ...

    def find_by_type(self, observation_type: ObservationType) -> list[ObservationContract]: ...

    def find_by_symbol(self, symbol: str) -> list[ObservationContract]: ...

    def find_by_producer(self, producer: str) -> list[ObservationContract]: ...


class InMemoryObservationRepository:
    """Reference implementation — for tests and local development only."""

    def __init__(self) -> None:
        self._by_id: dict[str, ObservationContract] = {}

    def save(self, observation: ObservationContract) -> None:
        self._by_id[observation.observation_id] = observation

    def get(self, observation_id: str) -> ObservationContract | None:
        return self._by_id.get(observation_id)

    def find_by_type(self, observation_type: ObservationType) -> list[ObservationContract]:
        return [o for o in self._by_id.values() if o.observation_type == observation_type]

    def find_by_symbol(self, symbol: str) -> list[ObservationContract]:
        return [o for o in self._by_id.values() if o.symbol == symbol]

    def find_by_producer(self, producer: str) -> list[ObservationContract]:
        return [o for o in self._by_id.values() if o.producer == producer]

    def count(self) -> int:
        return len(self._by_id)
