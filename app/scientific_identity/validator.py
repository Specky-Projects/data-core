"""ScientificIdentityValidator — structural and semantic validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.scientific_identity.contract import (
    ScientificEntityType,
    ScientificIdentity,
    ScientificIdentityChain,
)


class ValidationSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True)
class ValidationFinding:
    code: str
    severity: ValidationSeverity
    message: str


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    findings: tuple[ValidationFinding, ...] = ()

    def errors(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.severity == ValidationSeverity.ERROR]

    def warnings(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.severity == ValidationSeverity.WARNING]


# ── Expected lifecycle order ───────────────────────────────────────────────────

_CANONICAL_ORDER: list[ScientificEntityType] = [
    ScientificEntityType.OBSERVATION,
    ScientificEntityType.CONTEXT,
    ScientificEntityType.EVIDENCE,
    ScientificEntityType.CLAIM,
    ScientificEntityType.DECISION,
    ScientificEntityType.COMMITTEE,
    ScientificEntityType.PREVIEW,
    ScientificEntityType.EXECUTION,
    ScientificEntityType.OUTCOME,
    ScientificEntityType.REPLAY,
    ScientificEntityType.LEARNING,
    ScientificEntityType.EXPERIMENT,
    ScientificEntityType.KNOWLEDGE,
]

_ORDER_INDEX = {t: i for i, t in enumerate(_CANONICAL_ORDER)}


class ScientificIdentityValidator:
    """Validates individual identities and identity chains."""

    def validate_identity(self, identity: ScientificIdentity) -> ValidationResult:
        findings: list[ValidationFinding] = []

        for msg in identity.validate():
            findings.append(ValidationFinding(
                code="FIELD_ERROR",
                severity=ValidationSeverity.ERROR,
                message=msg,
            ))

        recomputed = identity.scientific_id
        if not recomputed:
            findings.append(ValidationFinding(
                code="HASH_FAILURE",
                severity=ValidationSeverity.ERROR,
                message="scientific_id could not be computed",
            ))

        if not identity.metadata and identity.entity_type not in {
            ScientificEntityType.CONTEXT,
            ScientificEntityType.REPLAY,
        }:
            findings.append(ValidationFinding(
                code="EMPTY_METADATA",
                severity=ValidationSeverity.WARNING,
                message=f"metadata is empty for entity_type={identity.entity_type}",
            ))

        return ValidationResult(
            valid=not any(f.severity == ValidationSeverity.ERROR for f in findings),
            findings=tuple(findings),
        )

    def validate_chain(self, chain: ScientificIdentityChain) -> ValidationResult:
        findings: list[ValidationFinding] = []

        for identity in chain.entries:
            result = self.validate_identity(identity)
            findings.extend(result.findings)

        types_seen = chain.entity_types()
        if types_seen and types_seen[0] != ScientificEntityType.OBSERVATION:
            findings.append(ValidationFinding(
                code="CHAIN_MUST_START_WITH_OBSERVATION",
                severity=ValidationSeverity.WARNING,
                message=(
                    f"chain starts with {types_seen[0]} instead of OBSERVATION — "
                    "full lifecycle traceability requires an Observation as the root"
                ),
            ))

        for i in range(1, len(types_seen)):
            prev_idx = _ORDER_INDEX.get(types_seen[i - 1], -1)
            curr_idx = _ORDER_INDEX.get(types_seen[i], -1)
            if curr_idx < prev_idx:
                findings.append(ValidationFinding(
                    code="CHAIN_ORDER_VIOLATION",
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"entity {types_seen[i]} at position {i} "
                        f"appears before expected position relative to {types_seen[i - 1]}"
                    ),
                ))

        if not chain.entries:
            findings.append(ValidationFinding(
                code="EMPTY_CHAIN",
                severity=ValidationSeverity.WARNING,
                message="chain has no entries",
            ))

        return ValidationResult(
            valid=not any(f.severity == ValidationSeverity.ERROR for f in findings),
            findings=tuple(findings),
        )
