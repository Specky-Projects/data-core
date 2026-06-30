"""
TEAM G — Business OS Universal Contracts
Multi-domain platform contracts. Every domain (Crypto, Affiliate, SEO, Social,
Sites, etc.) reuses the same scientific pipeline.
No domain-specific business logic in this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


BUSINESS_OS_CONTRACT_VERSION = "business-os-contracts-v1"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DomainKind(StrEnum):
    CRYPTO = "CRYPTO"
    AFFILIATE = "AFFILIATE"
    SEO = "SEO"
    SOCIAL = "SOCIAL"
    SITES = "SITES"
    REAL_ESTATE = "REAL_ESTATE"
    SPORTS = "SPORTS"
    RESEARCH = "RESEARCH"
    GENERIC = "GENERIC"


class MissionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class CapabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class ExecutionStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class OpportunityStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    EVALUATED = "EVALUATED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    CLOSED = "CLOSED"


class OutcomeKind(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    PARTIAL = "PARTIAL"
    INCONCLUSIVE = "INCONCLUSIVE"


class ProjectStatus(StrEnum):
    ACTIVE = "ACTIVE"
    STANDBY = "STANDBY"
    BLOCKED = "BLOCKED"
    ARCHIVED = "ARCHIVED"


# ---------------------------------------------------------------------------
# Mission
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MissionObjective:
    objective_id: str
    description: str
    metric: str
    target: float | None = None
    unit: str | None = None


@dataclass(frozen=True)
class Mission:
    mission_id: str
    domain: DomainKind
    title: str
    status: MissionStatus
    objectives: tuple[MissionObjective, ...]
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def active_objectives(self) -> tuple[MissionObjective, ...]:
        return self.objectives

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.mission_id:
            errors.append("mission_id is required")
        if not self.title:
            errors.append("mission.title is required")
        if not self.objectives:
            errors.append("mission must have at least one objective")
        return errors


# ---------------------------------------------------------------------------
# Capability
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CapabilityRef:
    capability_id: str
    kernel_ref: str
    description: str


@dataclass(frozen=True)
class DomainCapability:
    capability_id: str
    domain: DomainKind
    capability_ref: CapabilityRef
    status: CapabilityStatus
    version: str
    last_checked_at: str | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.capability_id:
            errors.append("capability_id is required")
        if not self.version:
            errors.append("version is required")
        return errors


# ---------------------------------------------------------------------------
# Execution Domain
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionDomainConfig:
    max_concurrent: int = 1
    retry_limit: int = 0
    advisory_only: bool = True


@dataclass(frozen=True)
class ExecutionDomain:
    domain_id: str
    kind: DomainKind
    pipeline_ref: str
    capabilities: tuple[DomainCapability, ...]
    config: ExecutionDomainConfig
    active: bool = True

    def has_capability(self, capability_id: str) -> bool:
        return any(c.capability_id == capability_id for c in self.capabilities)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.domain_id:
            errors.append("domain_id is required")
        if not self.pipeline_ref:
            errors.append("pipeline_ref is required")
        for cap in self.capabilities:
            errors.extend(cap.validate())
        return errors


# ---------------------------------------------------------------------------
# Opportunity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OpportunitySignal:
    signal_id: str
    source: str
    strength: float
    captured_at: str

    def validate(self) -> list[str]:
        if not 0.0 <= self.strength <= 1.0:
            return ["signal.strength must be between 0 and 1"]
        return []


@dataclass(frozen=True)
class Opportunity:
    opportunity_id: str
    domain: DomainKind
    status: OpportunityStatus
    signals: tuple[OpportunitySignal, ...]
    confidence: float
    expected_value: float | None
    discovered_at: str
    pipeline_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.opportunity_id:
            errors.append("opportunity_id is required")
        if not 0.0 <= self.confidence <= 1.0:
            errors.append("confidence must be between 0 and 1")
        for signal in self.signals:
            errors.extend(signal.validate())
        return errors


# ---------------------------------------------------------------------------
# Outcome
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Outcome:
    outcome_id: str
    domain: DomainKind
    opportunity_id: str
    kind: OutcomeKind
    realized_value: float | None
    expected_value: float | None
    recorded_at: str
    evidence_refs: tuple[str, ...] = ()
    learning_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def edge_delta(self) -> float | None:
        if self.realized_value is not None and self.expected_value is not None:
            return self.realized_value - self.expected_value
        return None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.outcome_id:
            errors.append("outcome_id is required")
        if not self.opportunity_id:
            errors.append("opportunity_id is required")
        return errors


# ---------------------------------------------------------------------------
# Learning (domain-level reference)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DomainLearningRef:
    """Points to universal learning layer — does not duplicate learning data."""

    ref_id: str
    domain: DomainKind
    snapshot_ref: str
    timeline_ref: str | None = None
    statistics_ref: str | None = None


# ---------------------------------------------------------------------------
# Knowledge
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DomainKnowledge:
    knowledge_id: str
    domain: DomainKind
    claim: str
    confidence: float
    evidence_refs: tuple[str, ...]
    created_at: str

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.knowledge_id:
            errors.append("knowledge_id is required")
        if not 0.0 <= self.confidence <= 1.0:
            errors.append("confidence must be between 0 and 1")
        if not self.evidence_refs:
            errors.append("domain knowledge must reference at least one evidence")
        return errors


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectExecution:
    execution_id: str
    project_id: str
    status: ExecutionStatus
    started_at: str
    finished_at: str | None = None
    opportunity_ref: str | None = None
    outcome_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.execution_id:
            errors.append("execution_id is required")
        if not self.project_id:
            errors.append("project_id is required")
        return errors


@dataclass(frozen=True)
class BusinessOSProject:
    project_id: str
    domain: DomainKind
    mission_ref: str
    status: ProjectStatus
    execution_domain: ExecutionDomain
    capabilities: tuple[DomainCapability, ...]
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.project_id:
            errors.append("project_id is required")
        if not self.mission_ref:
            errors.append("mission_ref is required")
        errors.extend(self.execution_domain.validate())
        for cap in self.capabilities:
            errors.extend(cap.validate())
        return errors


# ---------------------------------------------------------------------------
# Execution (cross-domain)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BusinessOSExecution:
    """
    Universal execution record across all Business OS domains.
    Backed by the scientific pipeline — never duplicates pipeline state.
    """

    execution_id: str
    domain: DomainKind
    project_id: str
    pipeline_id: str
    opportunity_id: str | None
    status: ExecutionStatus
    initiated_at: str
    completed_at: str | None = None
    outcome_ref: str | None = None
    learning_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.execution_id:
            errors.append("execution_id is required")
        if not self.project_id:
            errors.append("project_id is required")
        if not self.pipeline_id:
            errors.append("pipeline_id is required")
        return errors


# ---------------------------------------------------------------------------
# Platform registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BusinessOSRegistry:
    """Central registry of all active domains in the Business OS."""

    registry_id: str
    projects: tuple[BusinessOSProject, ...]
    domains: tuple[ExecutionDomain, ...]
    contract_version: str = BUSINESS_OS_CONTRACT_VERSION

    def project_for_domain(self, domain: DomainKind) -> tuple[BusinessOSProject, ...]:
        return tuple(p for p in self.projects if p.domain == domain)

    def active_domains(self) -> tuple[ExecutionDomain, ...]:
        return tuple(d for d in self.domains if d.active)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.registry_id:
            errors.append("registry_id is required")
        for project in self.projects:
            errors.extend(project.validate())
        for domain in self.domains:
            errors.extend(domain.validate())
        return errors
