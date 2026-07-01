"""Observation binding — projects a consumer decision's *facts* (never its
inferences) onto the canonical ObservationContract.

Per the Observation contract, an observation carries pure facts only — no
verdict, score, risk or prediction. We therefore expose the candidate and its
factual context (regime, evidence provenance, simulation flag), and leave the
posterior/verdict to later stages of the chain.
"""
from __future__ import annotations

from app.observation.contract import (
    ObservationContract,
    ObservationQuality,
    ObservationType,
    stable_hash,
)
from app.scientific_consumers.facts import DecisionFacts

_OBS_TYPE = {"CRYPTO": ObservationType.SIGNAL, "POUPI_BABY": ObservationType.GENERIC}


def build_observation(facts: DecisionFacts, scientific_identity_id: str | None = None) -> ObservationContract:
    payload = {
        "domain": facts.domain,
        "candidate_id": facts.candidate_id,
        "strategy": facts.strategy,
        "regime": facts.regime,
        "evidence_sources": sorted(e.source_name for e in facts.evidence),
        "evidence_count": len(facts.evidence),
        "simulation_only": facts.simulation_only,
        "observed_context_at": facts.decided_at,
    }
    return ObservationContract.create(
        observation_id=stable_hash({"lineage": facts.lineage_id, "kind": "observation"}),
        producer=facts.producer(),
        observed_at=facts.decided_at,
        observation_type=_OBS_TYPE.get(facts.domain, ObservationType.GENERIC),
        payload=payload,
        quality=ObservationQuality.VERIFIED if facts.evidence else ObservationQuality.RAW,
        symbol=facts.candidate_id,
        scientific_identity_id=scientific_identity_id,
        metadata={"consumer": facts.consumer, "read_only": True},
    )
