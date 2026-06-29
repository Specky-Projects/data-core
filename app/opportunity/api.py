"""Opportunity Platform API — Business OS 1.5.

FastAPI routes for opportunity endpoints.
All routes are replay-safe: wall-clock used only as default for evaluation_timestamp.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.adaptive_intelligence.dto import EvaluationContext
from app.knowledge.connectors.github import GitHubConnector
from app.knowledge.connectors.hacker_news import HackerNewsConnector
from app.knowledge.orchestrator import run_knowledge_pipeline
from app.opportunity.dto import (
    OPPORTUNITY_VERSION,
    OpportunityHealth,
    OpportunityReport,
    OpportunityVersionMetadata,
    RankingStrategy,
)
from app.opportunity.orchestrator import run_opportunity_pipeline

router = APIRouter(prefix="/opportunity", tags=["opportunity"])

# ── Query type aliases (Python-3.11-safe) ─────────────────────────────────────

EvalTimestampQuery = Annotated[datetime | None, Query()]
MaxItemsQuery = Annotated[int, Query(ge=1, le=200)]
WindowDaysQuery = Annotated[int, Query(ge=1, le=365)]
StrategyQuery = Annotated[RankingStrategy, Query()]


class OpportunityVersionResponse(BaseModel):
    opportunity_version: str
    versions: OpportunityVersionMetadata


class OpportunityHealthResponse(BaseModel):
    health: OpportunityHealth
    versions: OpportunityVersionMetadata


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.get("/version", response_model=OpportunityVersionResponse)
def get_opportunity_version() -> OpportunityVersionResponse:
    return OpportunityVersionResponse(
        opportunity_version=OPPORTUNITY_VERSION,
        versions=OpportunityVersionMetadata(),
    )


@router.get("/health", response_model=OpportunityHealthResponse)
def get_opportunity_health(
    evaluation_timestamp: EvalTimestampQuery = None,
    max_items: MaxItemsQuery = 10,
) -> OpportunityHealthResponse:
    ts = evaluation_timestamp or datetime.now(tz=timezone.utc)
    ctx = EvaluationContext(evaluation_timestamp=ts, dataset_version="live-1.5")
    connectors = [HackerNewsConnector(max_items=max_items)]
    knowledge_report = run_knowledge_pipeline(connectors, ctx)
    report = run_opportunity_pipeline(knowledge_report, ctx)
    return OpportunityHealthResponse(health=report.health, versions=report.versions)


@router.get("/report", response_model=OpportunityReport)
def get_opportunity_report(
    evaluation_timestamp: EvalTimestampQuery = None,
    max_items: MaxItemsQuery = 20,
    window_days: WindowDaysQuery = 30,
    strategy: StrategyQuery = RankingStrategy.BY_COMPOSITE,
) -> OpportunityReport:
    ts = evaluation_timestamp or datetime.now(tz=timezone.utc)
    ctx = EvaluationContext(evaluation_timestamp=ts, dataset_version="live-1.5")
    connectors = [
        HackerNewsConnector(max_items=max_items),
        GitHubConnector(topics=["machine-learning", "llm"], max_items=max_items),
    ]
    knowledge_report = run_knowledge_pipeline(connectors, ctx, correlation_window_days=window_days)
    return run_opportunity_pipeline(knowledge_report, ctx, ranking_strategy=strategy)
