from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.scientific_kernel.models import (
    KernelCapability,
    Portfolio,
    ScientificKernel,
    default_portfolio,
    default_scientific_kernel,
)


LOCAL_SCIENTIFIC_MARKERS = (
    "class Replay",
    "class Evidence",
    "class ScientificClaim",
    "class Counterfactual",
    "class KnowledgeGraph",
    "class AdaptiveIntelligence",
    "def replay_",
    "def counterfactual_",
    "def build_knowledge_graph",
)

CANONICAL_PATH_PARTS = (
    ("data-core", "app", "scientific_kernel"),
    ("data-core", "app", "knowledge"),
    ("data-core", "app", "adaptive_intelligence"),
    ("data-core", "app", "opportunity"),
    ("data-core", "app", "execution_runtime"),
)

IGNORED_PATH_PARTS = (
    ".claude",
    "__pycache__",
    ".venv",
    "node_modules",
    ".pytest_cache",
    "reports",
    "research_reports",
    "_poupi-baby-sprint1b-archive",
)


@dataclass(frozen=True)
class CertificationFinding:
    code: str
    status: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class CertificationResult:
    status: str
    kernel_version: str
    findings: tuple[CertificationFinding, ...] = field(default_factory=tuple)

    @property
    def go(self) -> bool:
        return self.status == "GO"


def _contains_parts(path: Path, parts: tuple[str, ...]) -> bool:
    lower_parts = tuple(part.lower() for part in path.parts)
    wanted = tuple(part.lower() for part in parts)
    return any(lower_parts[index:index + len(wanted)] == wanted for index in range(len(lower_parts)))


def _is_ignored(path: Path) -> bool:
    lower_parts = {part.lower() for part in path.parts}
    return any(part.lower() in lower_parts for part in IGNORED_PATH_PARTS)


def _is_canonical(path: Path) -> bool:
    return any(_contains_parts(path, parts) for parts in CANONICAL_PATH_PARTS)


def _module_path_exists(root: Path, module_ref: str) -> bool:
    return root.joinpath(*module_ref.split(".")).with_suffix(".py").exists()


def _scan_local_scientific_logic(root: Path) -> list[CertificationFinding]:
    findings: list[CertificationFinding] = []
    project_roots = [root / "poupi-baby", root / "poupi-crypto", root / "data-core"]
    for project_root in project_roots:
        if not project_root.exists():
            findings.append(CertificationFinding(
                code="PROJECT_ROOT_MISSING",
                status="NO_GO",
                message=f"Expected project root does not exist: {project_root.name}",
                path=str(project_root),
            ))
            continue
        for path in project_root.rglob("*.py"):
            if _is_ignored(path) or _is_canonical(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text(encoding="latin-1")
            markers = [marker for marker in LOCAL_SCIENTIFIC_MARKERS if marker in text]
            if markers:
                findings.append(CertificationFinding(
                    code="LOCAL_SCIENTIFIC_LOGIC",
                    status="NO_GO",
                    message=f"Scientific logic marker outside kernel boundary: {', '.join(markers)}",
                    path=str(path),
                ))
    return findings


def certify_workspace(
    root: str | Path,
    *,
    kernel: ScientificKernel | None = None,
    portfolio: Portfolio | None = None,
) -> CertificationResult:
    workspace_root = Path(root).resolve()
    active_kernel = kernel or default_scientific_kernel()
    active_portfolio = portfolio or default_portfolio()
    findings: list[CertificationFinding] = []

    for error in active_kernel.validate():
        findings.append(CertificationFinding("KERNEL_INVALID", "NO_GO", error))

    for capability, component in active_kernel.components.items():
        if capability in {
            KernelCapability.EXPERIMENT_ENGINE,
            KernelCapability.EXECUTION_MEMORY,
        }:
            # These references are kernel contracts that may be interface-only.
            continue
        if not _module_path_exists(workspace_root / "data-core", component.module_ref):
            findings.append(CertificationFinding(
                code="KERNEL_MODULE_MISSING",
                status="NO_GO",
                message=f"Kernel module missing for {capability.value}: {component.module_ref}",
            ))

    for error in active_portfolio.validate_against(active_kernel):
        findings.append(CertificationFinding("PORTFOLIO_INVALID", "NO_GO", error))

    findings.extend(_scan_local_scientific_logic(workspace_root))

    if not findings:
        findings.append(CertificationFinding(
            code="UNIFIED_SCIENTIFIC_PLATFORM",
            status="GO",
            message="Kernel, project model, memory boundary, and reuse policy are certified.",
        ))
        status = "GO"
    else:
        status = "NO_GO"

    return CertificationResult(
        status=status,
        kernel_version=active_kernel.version,
        findings=tuple(findings),
    )
