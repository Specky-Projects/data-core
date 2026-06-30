"""Business OS 5.0 — UEL Scientific Kernel Bridge.

Read-only facade that exposes the Ledger to the Scientific Kernel,
Execution Memory, Replay Engine, Opportunity Discovery, and Research pipelines.

No writes. No side effects. Only projection and filtering.

Future integrations:
  - ScientificKernel.load_execution_memory() → feed from UEL
  - ReplayEngine.load_corpus() → filter UEL by execution_type=REPLAY
  - CounterfactualEngine.load_baseline() → filter by relation=COUNTERFACTUAL
  - OpportunityDiscovery.evidence_feed() → evidence_ids from successful executions
  - ResearchPipeline.ingest() → learning_ids from completed executions
"""

from __future__ import annotations

from app.universal_execution_log.models import (
    ExecutionQuery,
    ExecutionRelation,
    ExecutionSurface,
    ExecutionType,
    UELStatus,
    UniversalExecution,
)
from app.universal_execution_log.protocol import UELLedgerProtocol


class ScientificLedgerBridge:
    """Read-only projection of the UEL for Scientific Kernel consumption.

    Accepts any UELLedgerProtocol-compatible backend (in-memory or DB).
    """

    def __init__(self, ledger: UELLedgerProtocol) -> None:
        self._ledger = ledger

    # ── Execution Memory ──────────────────────────────────────────────────────

    def load_execution_memory(
        self,
        project_id: str | None = None,
        limit: int = 500,
    ) -> list[UniversalExecution]:
        """Return completed executions for Scientific Memory ingestion."""
        return self._ledger.query_executions(
            ExecutionQuery(
                project_id=project_id,
                status=UELStatus.SUCCESS,
                limit=limit,
            )
        )

    # ── Replay corpus ─────────────────────────────────────────────────────────

    def load_replay_corpus(self, limit: int = 200) -> list[UniversalExecution]:
        """Return all replay executions for the Replay Engine."""
        return self._ledger.query_executions(
            ExecutionQuery(
                execution_surface=ExecutionSurface.REPLAY,
                limit=limit,
            )
        )

    # ── Counterfactual baseline ───────────────────────────────────────────────

    def load_counterfactual_baseline(
        self,
        capability_id: str,
        limit: int = 100,
    ) -> list[UniversalExecution]:
        """Return counterfactual executions for a given capability."""
        results = self._ledger.query_by_capability(capability_id)
        return [e for e in results if e.relation == ExecutionRelation.COUNTERFACTUAL][:limit]

    # ── Evidence feed ─────────────────────────────────────────────────────────

    def evidence_feed(
        self,
        project_id: str | None = None,
        limit: int = 1000,
    ) -> list[str]:
        """Return all evidence IDs from successful executions."""
        executions = self._ledger.query_executions(
            ExecutionQuery(project_id=project_id, status=UELStatus.SUCCESS, limit=limit)
        )
        ids: list[str] = []
        for e in executions:
            ids.extend(e.evidence_ids)
        return list(dict.fromkeys(ids))

    # ── Learning feed ─────────────────────────────────────────────────────────

    def learning_feed(
        self,
        project_id: str | None = None,
        limit: int = 1000,
    ) -> list[str]:
        """Return all learning IDs from completed executions."""
        executions = self._ledger.query_executions(
            ExecutionQuery(project_id=project_id, limit=limit)
        )
        ids: list[str] = []
        for e in executions:
            ids.extend(e.learning_ids)
        return list(dict.fromkeys(ids))

    # ── Research pipeline ─────────────────────────────────────────────────────

    def research_feed(self, limit: int = 500) -> list[UniversalExecution]:
        """Return research-type executions for the Research pipeline."""
        return self._ledger.query_executions(
            ExecutionQuery(
                execution_surface=ExecutionSurface.RESEARCH,
                status=UELStatus.SUCCESS,
                limit=limit,
            )
        )

    # ── Opportunity discovery ─────────────────────────────────────────────────

    def opportunity_evidence(
        self,
        mission_id: str,
        limit: int = 200,
    ) -> dict[str, object]:
        """Summarize execution outcomes for a mission (opportunity discovery)."""
        executions = self._ledger.query_by_mission(mission_id)[:limit]
        total = len(executions)
        if total == 0:
            return {"mission_id": mission_id, "total": 0, "evidence_ids": [], "value_delivered": False}
        successful = [e for e in executions if e.status == UELStatus.SUCCESS]
        all_evidence = []
        for e in successful:
            all_evidence.extend(e.evidence_ids)
        return {
            "mission_id": mission_id,
            "total": total,
            "successful": len(successful),
            "success_rate": len(successful) / total,
            "evidence_ids": list(dict.fromkeys(all_evidence)),
            "value_delivered": len(successful) > 0,
        }

    # ── Experiment executions ─────────────────────────────────────────────────

    def load_experiments(self, limit: int = 100) -> list[UniversalExecution]:
        return self._ledger.query_executions(
            ExecutionQuery(execution_surface=ExecutionSurface.EXPERIMENT, limit=limit)
        )

    # ── Simulation executions ─────────────────────────────────────────────────

    def load_simulations(self, limit: int = 100) -> list[UniversalExecution]:
        return self._ledger.query_executions(
            ExecutionQuery(status=UELStatus.SIMULATION, limit=limit)
        )
