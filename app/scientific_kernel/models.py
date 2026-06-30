from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


KERNEL_VERSION = "business-os-4.5-unified-scientific-platform"


class KernelCapability(str, Enum):
    EVIDENCE = "evidence"
    SCIENTIFIC_CLAIMS = "scientific_claims"
    REPLAY = "replay"
    COUNTERFACTUAL = "counterfactual"
    CAUSAL_ANALYSIS = "causal_analysis"
    EXPERIMENT_ENGINE = "experiment_engine"
    SCIENTIFIC_MEMORY = "scientific_memory"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    EXPLAINABILITY = "explainability"
    CONFIDENCE = "confidence"
    REPLAY_AUDIT = "replay_audit"
    REPLAY_METRICS = "replay_metrics"
    EXECUTION_MEMORY = "execution_memory"
    ADAPTIVE_INTELLIGENCE = "adaptive_intelligence"


class MemoryScope(str, Enum):
    GLOBAL_SCIENTIFIC = "global_scientific"
    PROJECT = "project"
    EXECUTION = "execution"
    BUSINESS = "business"
    RESEARCH = "research"
    KNOWLEDGE = "knowledge"


class ProjectKind(str, Enum):
    POUPI_BABY = "poupi_baby"
    MIRROR = "mirror"
    RESEARCH = "research"
    SINALO = "sinalo"
    FUTURE = "future"


@dataclass(frozen=True)
class KernelComponent:
    capability: KernelCapability
    module_ref: str
    owner: str
    version: str
    reusable: bool = True
    rollback_ref: str | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.module_ref:
            errors.append(f"{self.capability.value}: module_ref is required")
        if not self.owner:
            errors.append(f"{self.capability.value}: owner is required")
        if not self.version:
            errors.append(f"{self.capability.value}: version is required")
        if not self.reusable:
            errors.append(f"{self.capability.value}: kernel component must be reusable")
        return errors


@dataclass(frozen=True)
class Capability:
    capability_id: str
    kernel_capability: KernelCapability
    description: str
    required: bool = True


@dataclass(frozen=True)
class ExecutionSurface:
    surface_id: str
    surface_type: str
    project_id: str
    executes_only: bool = True

    def validate(self) -> list[str]:
        if not self.executes_only:
            return [f"{self.surface_id}: execution surface must not own intelligence"]
        return []


@dataclass(frozen=True)
class Mission:
    mission_id: str
    objective: str
    project_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Project:
    project_id: str
    kind: ProjectKind
    objective: str
    capabilities: tuple[Capability, ...] = ()
    surfaces: tuple[ExecutionSurface, ...] = ()
    memory_scopes: tuple[MemoryScope, ...] = (MemoryScope.PROJECT,)

    def validate_against(self, kernel: ScientificKernel) -> list[str]:
        errors: list[str] = []
        for capability in self.capabilities:
            if capability.kernel_capability not in kernel.components:
                errors.append(
                    f"{self.project_id}: missing kernel capability "
                    f"{capability.kernel_capability.value}"
                )
        for surface in self.surfaces:
            if surface.project_id != self.project_id:
                errors.append(f"{surface.surface_id}: project_id mismatch")
            errors.extend(surface.validate())
        return errors


@dataclass(frozen=True)
class Portfolio:
    portfolio_id: str
    mission: Mission
    projects: tuple[Project, ...]

    def validate_against(self, kernel: ScientificKernel) -> list[str]:
        errors: list[str] = []
        project_ids = {project.project_id for project in self.projects}
        for mission_project in self.mission.project_ids:
            if mission_project not in project_ids:
                errors.append(f"mission references unknown project: {mission_project}")
        for project in self.projects:
            errors.extend(project.validate_against(kernel))
        return errors


@dataclass(frozen=True)
class ScientificKernel:
    version: str
    components: dict[KernelCapability, KernelComponent] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        missing = sorted(set(KernelCapability) - set(self.components), key=lambda item: item.value)
        errors.extend(f"kernel missing capability: {capability.value}" for capability in missing)
        for component in self.components.values():
            errors.extend(component.validate())
        return errors

    def component_paths(self, root: Path) -> dict[KernelCapability, Path]:
        paths: dict[KernelCapability, Path] = {}
        for capability, component in self.components.items():
            module_parts = component.module_ref.split(".")
            if len(module_parts) < 2:
                continue
            paths[capability] = root.joinpath(*module_parts).with_suffix(".py")
        return paths


def _component(
    capability: KernelCapability,
    module_ref: str,
    version: str,
    rollback_ref: str,
) -> KernelComponent:
    return KernelComponent(
        capability=capability,
        module_ref=module_ref,
        owner="data-core/scientific-kernel",
        version=version,
        rollback_ref=rollback_ref,
    )


def default_scientific_kernel() -> ScientificKernel:
    return ScientificKernel(
        version=KERNEL_VERSION,
        components={
            KernelCapability.EVIDENCE: _component(
                KernelCapability.EVIDENCE,
                "app.knowledge.dto",
                "business-os-1.4-knowledge",
                "KnowledgeEvidence",
            ),
            KernelCapability.SCIENTIFIC_CLAIMS: _component(
                KernelCapability.SCIENTIFIC_CLAIMS,
                "app.knowledge.dto",
                "business-os-1.4-knowledge",
                "KnowledgeItem",
            ),
            KernelCapability.REPLAY: _component(
                KernelCapability.REPLAY,
                "app.adaptive_intelligence.dto",
                "business-os-1.3-stage-4",
                "EvaluationContext",
            ),
            KernelCapability.COUNTERFACTUAL: _component(
                KernelCapability.COUNTERFACTUAL,
                "app.adaptive_intelligence.dto",
                "business-os-1.3-stage-4",
                "DecisionQualityMetric",
            ),
            KernelCapability.CAUSAL_ANALYSIS: _component(
                KernelCapability.CAUSAL_ANALYSIS,
                "app.adaptive_intelligence.dto",
                "business-os-1.3-stage-4",
                "FeatureContribution",
            ),
            KernelCapability.EXPERIMENT_ENGINE: _component(
                KernelCapability.EXPERIMENT_ENGINE,
                "app.opportunity.evolution",
                "business-os-1.5-opportunity",
                "opportunity evolution contracts",
            ),
            KernelCapability.SCIENTIFIC_MEMORY: _component(
                KernelCapability.SCIENTIFIC_MEMORY,
                "app.knowledge.orchestrator",
                "business-os-1.4-knowledge",
                "KnowledgeReport",
            ),
            KernelCapability.KNOWLEDGE_GRAPH: _component(
                KernelCapability.KNOWLEDGE_GRAPH,
                "app.knowledge.graph",
                "business-os-1.4-knowledge",
                "LogicalKnowledgeGraph",
            ),
            KernelCapability.EXPLAINABILITY: _component(
                KernelCapability.EXPLAINABILITY,
                "app.adaptive_intelligence.dto",
                "business-os-1.3-stage-4",
                "ScientificLineage",
            ),
            KernelCapability.CONFIDENCE: _component(
                KernelCapability.CONFIDENCE,
                "app.adaptive_intelligence.confidence_calibration",
                "business-os-1.3-stage-4",
                "ConfidenceCalibrationResult",
            ),
            KernelCapability.REPLAY_AUDIT: _component(
                KernelCapability.REPLAY_AUDIT,
                "app.adaptive_intelligence.dto",
                "business-os-1.3-stage-4",
                "ScientificLearningHealth",
            ),
            KernelCapability.REPLAY_METRICS: _component(
                KernelCapability.REPLAY_METRICS,
                "app.adaptive_intelligence.metrics",
                "business-os-1.3-stage-4",
                "adaptive learning metrics",
            ),
            KernelCapability.EXECUTION_MEMORY: _component(
                KernelCapability.EXECUTION_MEMORY,
                "app.execution_runtime.orchestrator",
                "business-os-execution-runtime",
                "execution runtime records",
            ),
            KernelCapability.ADAPTIVE_INTELLIGENCE: _component(
                KernelCapability.ADAPTIVE_INTELLIGENCE,
                "app.adaptive_intelligence.orchestrator",
                "business-os-1.3-stage-4",
                "AdaptiveIntelligenceOrchestrator",
            ),
        },
    )


def required_scientific_capabilities() -> tuple[Capability, ...]:
    return tuple(
        Capability(
            capability_id=f"capability.{capability.value}",
            kernel_capability=capability,
            description=f"Consume {capability.value} from the scientific kernel.",
        )
        for capability in KernelCapability
    )


def default_portfolio() -> Portfolio:
    capabilities = required_scientific_capabilities()
    projects = (
        Project("poupi-baby", ProjectKind.POUPI_BABY, "Savings and affiliate commerce", capabilities),
        Project("mirror", ProjectKind.MIRROR, "Signal mirroring and execution observation", capabilities),
        Project("research", ProjectKind.RESEARCH, "Global opportunity discovery", capabilities),
        Project("sinalo", ProjectKind.SINALO, "Future signal product surface", capabilities),
    )
    return Portfolio(
        portfolio_id="poupi-ecosystem",
        mission=Mission(
            mission_id="unified-scientific-platform",
            objective="Share one scientific infrastructure across POUPI projects.",
            project_ids=tuple(project.project_id for project in projects),
        ),
        projects=projects,
    )
