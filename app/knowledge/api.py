"""Knowledge Platform API — Business OS 1.4.

FastAPI routes for knowledge pipeline endpoints.
All routes are replay-safe: wall-clock is only used as default for evaluation_timestamp.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.adaptive_intelligence.dto import EvaluationContext
from app.knowledge.connectors.github import GitHubConnector
from app.knowledge.connectors.hacker_news import HackerNewsConnector
from app.knowledge.dto import (
    KnowledgeHealth,
    KnowledgeReport,
    KnowledgeVersionMetadata,
    KNOWLEDGE_VERSION,
)
from app.knowledge.orchestrator import run_knowledge_pipeline

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# ── Query type aliases (FastAPI/Python-3.11-compatible) ────────────────────────

EvalTimestampQuery = Annotated[datetime | None, Query()]
MaxItemsQuery = Annotated[int, Query(ge=1, le=200)]
WindowDaysQuery = Annotated[int, Query(ge=1, le=365)]


class KnowledgeVersionResponse(BaseModel):
    knowledge_version: str
    versions: KnowledgeVersionMetadata


class KnowledgeHealthResponse(BaseModel):
    health: KnowledgeHealth
    versions: KnowledgeVersionMetadata


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.get("/version", response_model=KnowledgeVersionResponse)
def get_knowledge_version() -> KnowledgeVersionResponse:
    return KnowledgeVersionResponse(
        knowledge_version=KNOWLEDGE_VERSION,
        versions=KnowledgeVersionMetadata(),
    )


@router.get("/health", response_model=KnowledgeHealthResponse)
def get_knowledge_health(
    evaluation_timestamp: EvalTimestampQuery = None,
    max_items: MaxItemsQuery = 10,
    window_days: WindowDaysQuery = 30,
) -> KnowledgeHealthResponse:
    ts = evaluation_timestamp or datetime.now(tz=timezone.utc)
    evaluation_context = EvaluationContext(evaluation_timestamp=ts, dataset_version="live-1.4")

    connectors = [
        HackerNewsConnector(max_items=max_items),
    ]
    report = run_knowledge_pipeline(
        connectors=connectors,
        evaluation_context=evaluation_context,
        correlation_window_days=window_days,
    )
    return KnowledgeHealthResponse(
        health=report.health,
        versions=report.versions,
    )


@router.get("/report", response_model=KnowledgeReport)
def get_knowledge_report(
    evaluation_timestamp: EvalTimestampQuery = None,
    max_items: MaxItemsQuery = 20,
    window_days: WindowDaysQuery = 30,
) -> KnowledgeReport:
    ts = evaluation_timestamp or datetime.now(tz=timezone.utc)
    evaluation_context = EvaluationContext(evaluation_timestamp=ts, dataset_version="live-1.4")

    connectors = [
        HackerNewsConnector(max_items=max_items),
        GitHubConnector(topics=["machine-learning", "llm"], max_items=max_items),
    ]
    return run_knowledge_pipeline(
        connectors=connectors,
        evaluation_context=evaluation_context,
        correlation_window_days=window_days,
    )
