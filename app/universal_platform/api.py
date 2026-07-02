"""Universal Platform — FastAPI router.

Public, advisory-only, read-only. Exposes a status probe plus two read-only
aggregate views (daily brief, alerts) — no endpoint here can trigger, mutate, or
gate anything in Mirror, Crypto, Committee, Executor, Risk, Position Sizing,
Kill Switch, or Research Lab.

The aggregate routes add NO business logic: they route through the existing
``Phase2Platform.execute(...)`` capability path, which reuses
``DailyBriefBuilder.build()`` and ``UnifiedAlertEngine.evaluate()`` verbatim.

Prefix: /universal-platform
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from app.universal_platform.bootstrap import get_platform, platform_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/universal-platform", tags=["universal-platform"])


class AggregateQuery(BaseModel):
    """Optional input for the aggregate views.

    The universal runtime is stateless — brief/alerts are computed from the
    ``events`` supplied here. With no events the aggregate is well-formed but
    empty. This mirrors the existing capability handlers' input contract; it
    introduces no new logic.
    """

    events: list[dict] = Field(default_factory=list)
    generated_at: str = ""


def _unavailable(extra: dict) -> dict:
    """Advisory 'platform unavailable' payload — these routes never raise."""
    return {"initialized": False, "advisory_only": True, **extra}


@router.get("/status", include_in_schema=False)
def status() -> dict:
    """Advisory-only status of the Universal Platform (Phase 2).

    Returns ``initialized: false`` instead of erroring if the platform failed
    to boot — this endpoint never raises.
    """
    return platform_status()


@router.get("/daily-brief", include_in_schema=False)
def daily_brief(query: Annotated[AggregateQuery | None, Body()] = None) -> dict:
    """Read-only unified daily brief.

    Reuses ``DailyBriefBuilder.build()`` (via the ``daily_brief.generate``
    capability) with zero new logic. Advisory-only; never raises.
    """
    platform = get_platform()
    if platform is None:
        return _unavailable({"sections": [], "scientific_health": 0.0})
    q = query or AggregateQuery()
    try:
        response = platform.execute(
            "daily_brief.generate",
            {"events": q.events, "generated_at": q.generated_at},
        )
    except Exception as exc:  # noqa: BLE001 — advisory endpoint must never 500
        logger.exception("universal_platform.daily_brief: execute failed")
        return _unavailable({"error": str(exc), "sections": [], "scientific_health": 0.0})
    return {"initialized": True, "advisory_only": True, **response.outputs}


@router.get("/alerts", include_in_schema=False)
def alerts(query: Annotated[AggregateQuery | None, Body()] = None) -> dict:
    """Read-only correlated alerts.

    Reuses ``UnifiedAlertEngine.evaluate()`` (via the ``alert.evaluate``
    capability) with zero new logic. Advisory-only; never raises.
    """
    platform = get_platform()
    if platform is None:
        return _unavailable({"alerts": [], "count": 0})
    q = query or AggregateQuery()
    try:
        response = platform.execute("alert.evaluate", {"events": q.events})
    except Exception as exc:  # noqa: BLE001 — advisory endpoint must never 500
        logger.exception("universal_platform.alerts: execute failed")
        return _unavailable({"error": str(exc), "alerts": [], "count": 0})
    return {"initialized": True, "advisory_only": True, **response.outputs}
