"""ReuseChecker — REUTILIZAR → ESTENDER → GENERALIZAR → CRIAR NOVO."""
from __future__ import annotations

from typing import Any

from app.development_engine.contracts import ReuseAction, ReuseCheckResult

# Known reusable modules in data-core
_KNOWN_MODULES = [
    {"module": "scientific_identity", "exports": ["stable_hash", "ScientificIdentity"]},
    {"module": "scientific_kernel", "exports": ["ScientificEvidence", "EvidenceKind", "EvidenceQuality"]},
    {"module": "observation", "exports": ["ObservationContract", "ObservationRepository"]},
    {"module": "business_os", "exports": ["DomainKind", "Opportunity", "Outcome"]},
    {"module": "explainability_v2", "exports": ["ExplanationContract"]},
    {"module": "universal_learning", "exports": ["LearningContract"]},
    {"module": "execution_runtime", "exports": ["ReplayEngine"]},
    {"module": "knowledge", "exports": ["KnowledgeGraph"]},
]


class ReuseCheckerCapability:
    name = "reuse_checker"

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        concept = inputs.get("concept", "")
        candidates = [m for m in _KNOWN_MODULES if any(
            concept.lower() in export.lower() or concept.lower() in m["module"].lower()
            for export in m["exports"]
        )]

        if candidates:
            if len(candidates) == 1:
                action = ReuseAction.REUSE
                rationale = f"Exact match found in {candidates[0]['module']}"
            else:
                action = ReuseAction.EXTEND
                rationale = f"Multiple candidates — extend the most specific: {candidates[0]['module']}"
        else:
            action = ReuseAction.CREATE_NEW
            rationale = f"No existing module found for concept '{concept}'"

        result = ReuseCheckResult(
            action=action,
            candidates=candidates,
            rationale=rationale,
            evidence=[f"module:{m['module']}" for m in candidates],
            advisory_only=True,
        )
        return {
            "action": str(result.action),
            "candidates": result.candidates,
            "rationale": result.rationale,
            "evidence": result.evidence,
            "advisory_only": result.advisory_only,
        }
