from pathlib import Path

from app.scientific_kernel.certification import certify_workspace
from app.scientific_kernel.models import (
    KernelCapability,
    default_portfolio,
    default_scientific_kernel,
)


def test_default_kernel_declares_every_scientific_capability() -> None:
    kernel = default_scientific_kernel()

    assert set(kernel.components) == set(KernelCapability)
    assert kernel.validate() == []


def test_default_portfolio_consumes_kernel_capabilities() -> None:
    kernel = default_scientific_kernel()
    portfolio = default_portfolio()

    assert portfolio.validate_against(kernel) == []
    assert {project.project_id for project in portfolio.projects} == {
        "poupi-baby",
        "mirror",
        "research",
        "sinalo",
    }


def test_certification_fails_closed_for_local_scientific_logic(tmp_path: Path) -> None:
    for project in ("poupi-baby", "poupi-crypto", "data-core"):
        (tmp_path / project).mkdir()
    local_module = tmp_path / "poupi-baby" / "local_replay.py"
    local_module.write_text("class Replay:\n    pass\n", encoding="utf-8")

    result = certify_workspace(tmp_path)

    assert result.status == "NO_GO"
    assert any(finding.code == "LOCAL_SCIENTIFIC_LOGIC" for finding in result.findings)


def test_certification_allows_canonical_kernel_logic(tmp_path: Path) -> None:
    for project in ("poupi-baby", "poupi-crypto"):
        (tmp_path / project).mkdir()
    canonical = tmp_path / "data-core" / "app" / "scientific_kernel"
    canonical.mkdir(parents=True)
    (canonical / "replay.py").write_text("class Replay:\n    pass\n", encoding="utf-8")

    result = certify_workspace(tmp_path, kernel=default_scientific_kernel())

    assert not any(finding.code == "LOCAL_SCIENTIFIC_LOGIC" for finding in result.findings)
