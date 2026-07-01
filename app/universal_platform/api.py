"""Universal Platform — FastAPI router.

Public, advisory-only, read-only. Exposes only a status probe — no endpoint
here can trigger, mutate, or gate anything in Mirror, Crypto, Committee,
Executor, Risk, Position Sizing, Kill Switch, or Research Lab.

Prefix: /universal-platform
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

from app.universal_platform.bootstrap import platform_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/universal-platform", tags=["universal-platform"])


@router.get("/status", include_in_schema=False)
def status() -> dict:
    """Advisory-only status of the Universal Platform (Phase 2).

    Returns ``initialized: false`` instead of erroring if the platform failed
    to boot — this endpoint never raises.
    """
    return platform_status()
