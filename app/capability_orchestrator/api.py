"""Capability Registry — read-only HTTP projection.

This module does **not** define a new registry, orchestrator, schema, catalog or
source of truth. It is a thin, stateless projection of the *existing*
``CapabilityRegistry`` populated by the *existing* platform bootstraps:

  • ``BusinessOSPlatform.startup()``  → the 7 engine capabilities (SoT)
  • ``Phase2Platform``                → the universal-platform capabilities (SoT)

Both already build their registries via their own ``register()`` logic; here we
merely read ``registry.all()`` and serialize each ``CapabilityRegistration`` to
JSON. No cache, no duplicate DTO, no business logic — pure projection.

Consumers (e.g. Mission Control) MUST reach capabilities through these
endpoints, never by importing engines directly.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.capability_orchestrator.contracts import CapabilityKind, CapabilityRegistration

router = APIRouter(prefix="/capabilities", tags=["capability-registry"])


def _load_registrations() -> list[tuple[str, CapabilityRegistration]]:
    """Build the live registrations from the existing bootstraps.

    Each entry is ``(source_platform, registration)``. Built per-request and
    thrown away — the registrations are pure in-memory specs (no I/O), so there
    is no parallel cache and no second source of truth. Each bootstrap is
    guarded independently so one failing does not blank the whole projection.
    """
    out: list[tuple[str, CapabilityRegistration]] = []
    seen: set[str] = set()

    # Business OS — 7 engines register into one orchestrator/registry.
    try:
        from app.business_os_platform import BusinessOSPlatform

        platform = BusinessOSPlatform()
        platform.startup()
        for reg in platform.orchestrator.registry.all():
            if reg.capability_id not in seen:
                seen.add(reg.capability_id)
                out.append(("business-os", reg))
    except Exception:  # pragma: no cover - degrade, never 500 the projection
        pass

    # Universal Platform — adapters/runtime/brief/alerts capabilities.
    try:
        from app.universal_platform.capabilities import Phase2Platform

        p2 = Phase2Platform()
        for reg in p2.registry.all():
            if reg.capability_id not in seen:
                seen.add(reg.capability_id)
                out.append(("universal-platform", reg))
    except Exception:  # pragma: no cover
        pass

    return out


def _project(source: str, reg: CapabilityRegistration) -> dict:
    """Serialize one registration. Derived fields only — no schema mutation."""
    return {
        "capability_id": reg.capability_id,
        "kind": reg.kind.value,
        "name": reg.name,
        "version": reg.version,
        "description": reg.description,
        "input_schema": reg.input_schema,
        "output_schema": reg.output_schema,
        "dependencies": list(reg.dependencies),
        "advisory_only": reg.advisory_only,
        "owner": reg.owner,
        # source_platform is the SoT bootstrap that registered it (derived,
        # not part of CapabilityRegistration — helps callers trace ownership).
        "source_platform": source,
        "registered_at": reg.registered_at.isoformat() if reg.registered_at else None,
    }


@router.get("", summary="List all registered capabilities (read-only projection)")
@router.get("/", include_in_schema=False)
def list_capabilities() -> dict:
    registrations = _load_registrations()
    items = [_project(src, reg) for src, reg in registrations]
    kinds: dict[str, int] = {}
    for _, reg in registrations:
        kinds[reg.kind.value] = kinds.get(reg.kind.value, 0) + 1
    return {
        "total": len(items),
        "kinds": kinds,
        "advisory_only": all(reg.advisory_only for _, reg in registrations),
        "capabilities": items,
    }


@router.get("/kind/{kind}", summary="List capabilities of a given kind")
def list_capabilities_by_kind(kind: str) -> dict:
    try:
        parsed = CapabilityKind(kind.lower())
    except ValueError:
        valid = [k.value for k in CapabilityKind]
        raise HTTPException(status_code=404, detail=f"Unknown kind '{kind}'. Valid: {valid}")
    items = [
        _project(src, reg)
        for src, reg in _load_registrations()
        if reg.kind == parsed
    ]
    return {"kind": parsed.value, "total": len(items), "capabilities": items}


@router.get("/{capability_id}", summary="Get a single capability by id")
def get_capability(capability_id: str) -> dict:
    for src, reg in _load_registrations():
        if reg.capability_id == capability_id:
            return _project(src, reg)
    raise HTTPException(status_code=404, detail=f"Capability '{capability_id}' not registered")
