"""TruthCandidateFactory — creates TruthCandidates from ObservationRecords."""
from __future__ import annotations

import uuid

from app.knowledge_engine.contracts import KnowledgeScope, TruthCandidate
from app.scientific_identity.contract import stable_hash


class TruthCandidateFactory:
    def from_observation_dict(self, obs: dict) -> TruthCandidate:
        """Create a TruthCandidate from an observation dict (serialized ObservationRecord)."""
        observation_id = obs.get("observation_id", str(uuid.uuid4()))
        project = obs.get("project", "unknown")
        domain = obs.get("domain", "GENERIC")
        health = obs.get("health", "UNKNOWN")

        # Map health to confidence
        confidence_map = {"HEALTHY": 0.8, "DEGRADED": 0.5, "CRITICAL": 0.3, "UNKNOWN": 0.4}
        confidence = confidence_map.get(health, 0.4)

        return TruthCandidate(
            candidate_id=stable_hash({"obs": observation_id, "project": project}),
            observation_id=observation_id,
            proposition=f"System {project} reported health={health}",
            domain=domain,
            project=project,
            confidence=confidence,
            evidence=[f"observation:{observation_id}"],
            advisory_only=True,
        )
