"""Business OS 4.5 unified scientific kernel.

The kernel is a registry and governance boundary over existing certified
scientific components. It does not duplicate replay, evidence, memory,
knowledge graph, adaptive intelligence, or explainability logic.
"""

from app.scientific_kernel.certification import (
    CertificationFinding,
    CertificationResult,
    certify_workspace,
)
from app.scientific_kernel.models import (
    Capability,
    ExecutionSurface,
    KernelCapability,
    KernelComponent,
    MemoryScope,
    Mission,
    Portfolio,
    Project,
    ProjectKind,
    ScientificKernel,
    default_scientific_kernel,
)

__all__ = [
    "Capability",
    "CertificationFinding",
    "CertificationResult",
    "ExecutionSurface",
    "KernelCapability",
    "KernelComponent",
    "MemoryScope",
    "Mission",
    "Portfolio",
    "Project",
    "ProjectKind",
    "ScientificKernel",
    "certify_workspace",
    "default_scientific_kernel",
]
