"""ObservationTimeline — ordered sequence of observations for a lineage."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.observation.contract import ObservationContract, ObservationType, stable_hash


@dataclass
class ObservationTimeline:
    """Ordered, append-only timeline of observations for one scientific lineage.

    ``lineage_id`` links the timeline to a ScientificIdentityChain.
    Observations are kept in insertion order (producer's responsibility
    to insert in chronological order).
    """

    lineage_id: str
    observations: list[ObservationContract] = field(default_factory=list)

    def append(self, observation: ObservationContract) -> None:
        errors = observation.validate()
        if errors:
            raise ValueError(f"invalid observation: {errors}")
        self.observations.append(observation)

    def by_type(self, observation_type: ObservationType) -> list[ObservationContract]:
        return [o for o in self.observations if o.observation_type == observation_type]

    def by_symbol(self, symbol: str) -> list[ObservationContract]:
        return [o for o in self.observations if o.symbol == symbol]

    def first(self) -> ObservationContract | None:
        return self.observations[0] if self.observations else None

    def latest(self) -> ObservationContract | None:
        return self.observations[-1] if self.observations else None

    def count(self) -> int:
        return len(self.observations)

    @property
    def timeline_hash(self) -> str:
        """Deterministic hash of the full timeline — changes if any observation changes."""
        return stable_hash([o.observation_id for o in self.observations])

    def replay_window(
        self,
        from_observed_at: str,
        until_observed_at: str,
    ) -> list[ObservationContract]:
        """Return observations within a closed time window [from, until]."""
        return [
            o for o in self.observations
            if from_observed_at <= o.observed_at <= until_observed_at
        ]
