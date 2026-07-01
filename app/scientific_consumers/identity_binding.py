"""ScientificIdentity binding — builds the deterministic identity chain for a
consumer decision: Observation → Context → Evidence → Claim → Decision →
Committee → Preview → [Outcome] → [Learning].

All identities share one lineage_id (derived deterministically from the
decision) and are linked parent→child. produced_at is taken from the decision's
own timestamp so the chain is byte-stable across replays.
"""
from __future__ import annotations

from app.scientific_consumers.facts import DecisionFacts
from app.scientific_identity.builder import ScientificIdentityBuilder
from app.scientific_identity.contract import ScientificEntityType, ScientificIdentityChain

# Ordered lifecycle stages materialised as identities.
_CORE_STAGES: tuple[ScientificEntityType, ...] = (
    ScientificEntityType.OBSERVATION,
    ScientificEntityType.CONTEXT,
    ScientificEntityType.EVIDENCE,
    ScientificEntityType.CLAIM,
    ScientificEntityType.DECISION,
    ScientificEntityType.COMMITTEE,
    ScientificEntityType.PREVIEW,
)


def build_identity_chain(facts: DecisionFacts) -> ScientificIdentityChain:
    builder = ScientificIdentityBuilder(facts.lineage_id, facts.producer()).with_metadata(
        {"consumer": facts.consumer, "decision_id": facts.decision_id, "advisory_only": True}
    )
    chain = ScientificIdentityBuilder.new_chain(facts.lineage_id)

    stages = list(_CORE_STAGES)
    if facts.outcome is not None:
        stages.append(ScientificEntityType.OUTCOME)
        stages.append(ScientificEntityType.LEARNING)
        stages.append(ScientificEntityType.KNOWLEDGE)

    for entity_type in stages:
        entity_id = f"{facts.decision_id}:{entity_type.value.lower()}"
        _, chain = builder.build_chain(
            entity_type=entity_type,
            entity_id=entity_id,
            chain=chain,
            produced_at=facts.decided_at,
        )
    return chain


def decision_identity_id(facts: DecisionFacts) -> str:
    """The scientific_id of the DECISION node — the canonical handle for a decision."""
    for identity in build_identity_chain(facts).entries:
        if identity.entity_type is ScientificEntityType.DECISION:
            return identity.scientific_id
    raise RuntimeError("DECISION identity missing from chain")
