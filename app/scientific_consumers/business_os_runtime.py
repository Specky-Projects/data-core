"""Business OS runtime registration for Phase 3.0 consumers."""
from __future__ import annotations

from app.business_os.contracts import (
    BusinessOSProject,
    BusinessOSRegistry,
    CapabilityRef,
    CapabilityStatus,
    DomainCapability,
    DomainKind,
    ExecutionDomain,
    ExecutionDomainConfig,
    Mission,
    MissionObjective,
    MissionStatus,
    Opportunity,
    OpportunitySignal,
    OpportunityStatus,
    Outcome,
    OutcomeKind,
    ProjectStatus,
)
from app.scientific_consumers.facts import DecisionFacts
from app.scientific_identity.contract import stable_hash


def _capability(domain: DomainKind, capability_id: str, description: str) -> DomainCapability:
    return DomainCapability(
        capability_id=capability_id,
        domain=domain,
        capability_ref=CapabilityRef(
            capability_id=capability_id,
            kernel_ref="scientific-runtime-consumers-v1",
            description=description,
        ),
        status=CapabilityStatus.AVAILABLE,
        version="phase-3.0",
        last_checked_at="2026-06-30",
    )


def build_crypto_execution_domain() -> ExecutionDomain:
    capabilities = (
        _capability(DomainKind.CRYPTO, "mirror-scientific-observation", "Mirror scientific runtime observer"),
        _capability(DomainKind.CRYPTO, "mirror-replay-certification", "Mirror deterministic replay binding"),
    )
    return ExecutionDomain(
        domain_id="execution-domain:crypto",
        kind=DomainKind.CRYPTO,
        pipeline_ref="scientific-pipeline-v1",
        capabilities=capabilities,
        config=ExecutionDomainConfig(max_concurrent=1, retry_limit=0, advisory_only=True),
        active=True,
    )


def build_poupi_baby_execution_domain() -> ExecutionDomain:
    capabilities = (
        _capability(DomainKind.AFFILIATE, "poupi-baby-recommendation", "Poupi Baby supervised recommendations"),
        _capability(DomainKind.AFFILIATE, "poupi-baby-learning-feed", "Poupi Baby advisory learning feed"),
    )
    return ExecutionDomain(
        domain_id="execution-domain:poupi-baby",
        kind=DomainKind.AFFILIATE,
        pipeline_ref="scientific-pipeline-v1",
        capabilities=capabilities,
        config=ExecutionDomainConfig(max_concurrent=1, retry_limit=0, advisory_only=True),
        active=True,
    )


def build_business_os_registry() -> BusinessOSRegistry:
    crypto = build_crypto_execution_domain()
    baby = build_poupi_baby_execution_domain()
    crypto_project = BusinessOSProject(
        project_id="project:mirror-runtime-consumer",
        domain=DomainKind.CRYPTO,
        mission_ref="mission:crypto-runtime-observability",
        status=ProjectStatus.ACTIVE,
        execution_domain=crypto,
        capabilities=crypto.capabilities,
        created_at="2026-06-30",
        metadata={"consumer": "mirror", "read_only": True},
    )
    baby_project = BusinessOSProject(
        project_id="project:poupi-baby-runtime-consumer",
        domain=DomainKind.AFFILIATE,
        mission_ref="mission:poupi-baby-supervised-recommendations",
        status=ProjectStatus.ACTIVE,
        execution_domain=baby,
        capabilities=baby.capabilities,
        created_at="2026-06-30",
        metadata={"consumer": "poupi-baby", "advisory_only": True},
    )
    return BusinessOSRegistry(
        registry_id="business-os:phase-3-runtime-consumers",
        projects=(crypto_project, baby_project),
        domains=(crypto, baby),
    )


def build_mission(facts: DecisionFacts) -> Mission:
    kind = DomainKind.CRYPTO if facts.domain == "CRYPTO" else DomainKind.AFFILIATE
    return Mission(
        mission_id=stable_hash({"lineage": facts.lineage_id, "kind": "mission"}),
        domain=kind,
        title=f"{facts.consumer} scientific runtime consumption",
        status=MissionStatus.ACTIVE,
        objectives=(
            MissionObjective(
                objective_id=stable_hash({"lineage": facts.lineage_id, "kind": "objective"}),
                description="Maintain advisory-only scientific traceability.",
                metric="trace_continuity",
                target=1.0,
                unit="ratio",
            ),
        ),
        created_at=facts.decided_at,
        metadata={"lineage_id": facts.lineage_id},
    )


def build_opportunity(facts: DecisionFacts, pipeline_id: str) -> Opportunity:
    kind = DomainKind.CRYPTO if facts.domain == "CRYPTO" else DomainKind.AFFILIATE
    signals = tuple(
        OpportunitySignal(
            signal_id=e.evidence_id,
            source=e.source_name,
            strength=e.quality_score if e.quality_score is not None else facts.confidence,
            captured_at=facts.decided_at,
        )
        for e in facts.evidence
    ) or (
        OpportunitySignal(
            signal_id=stable_hash({"lineage": facts.lineage_id, "kind": "default_signal"}),
            source=facts.consumer,
            strength=facts.confidence,
            captured_at=facts.decided_at,
        ),
    )
    return Opportunity(
        opportunity_id=facts.decision_id,
        domain=kind,
        status=OpportunityStatus.EVALUATED,
        signals=signals,
        confidence=facts.confidence,
        expected_value=facts.expected_edge,
        discovered_at=facts.decided_at,
        pipeline_ref=pipeline_id,
        evidence_refs=tuple(e.evidence_id for e in facts.evidence),
        metadata={"lineage_id": facts.lineage_id, "consumer": facts.consumer},
    )


def build_outcome(facts: DecisionFacts) -> Outcome | None:
    if facts.outcome is None:
        return None
    kind = DomainKind.CRYPTO if facts.domain == "CRYPTO" else DomainKind.AFFILIATE
    return Outcome(
        outcome_id=stable_hash({"lineage": facts.lineage_id, "kind": "business_os_outcome"}),
        domain=kind,
        opportunity_id=facts.decision_id,
        kind=OutcomeKind(facts.outcome.kind),
        realized_value=facts.outcome.realized_value,
        expected_value=facts.outcome.expected_value,
        recorded_at=facts.outcome.recorded_at,
        evidence_refs=tuple(e.evidence_id for e in facts.evidence),
        learning_ref=stable_hash({"lineage": facts.lineage_id, "kind": "learning_signal"}),
        metadata={"lineage_id": facts.lineage_id, "consumer": facts.consumer},
    )
