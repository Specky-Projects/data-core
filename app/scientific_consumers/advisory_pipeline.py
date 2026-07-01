"""AdvisoryDecisionPipeline — a concrete, deterministic implementation of the
canonical ScientificDecisionPipeline contract.

It does NOT decide anything operationally. It replays the stages a consumer
decision already went through (CONTEXT → EVIDENCE → BAYESIAN → COMMITTEE →
EXPLAINABILITY → PREVIEW → [LEARNING]) purely to *record* them as a canonical
PipelineTrace. The final PREVIEW stage carries the verdict/action exactly as
the consumer produced it — never re-derived — and is always advisory.

Determinism: every stage output is a pure function of the immutable
PipelineContext seed, so run() and replay() yield byte-identical hashes.
"""
from __future__ import annotations

from typing import Any

from app.scientific_consumers.facts import DecisionFacts
from app.scientific_pipeline.contracts import (
    STAGE_CONTRACTS,
    STAGE_ORDER,
    PipelineContext,
    PipelineReplayManifest,
    PipelineState,
    PipelineStatus,
    PipelineTrace,
    ReplayInput,
    ScientificDecisionPipeline,
    StageKind,
    StageOutput,
    StageStatus,
    StageTrace,
)
from app.scientific_identity.contract import stable_hash

ADVISORY_ONLY = True


def build_pipeline_context(facts: DecisionFacts) -> PipelineContext:
    """Deterministic PipelineContext whose metadata seed drives every stage."""
    seed = {
        "domain": facts.domain,
        "candidate_id": facts.candidate_id,
        "strategy": facts.strategy,
        "regime": facts.regime,
        "decided_at": facts.decided_at,
        "prior": facts.prior,
        "likelihood": facts.likelihood,
        "posterior": facts.posterior,
        "confidence": facts.confidence,
        "evidence_weight": facts.evidence_weight,
        "evidence_sources": sorted(e.source_name for e in facts.evidence),
        "committee_verdict": facts.committee_verdict,
        "committee_confidence": facts.committee_confidence,
        "committee_quorum_met": facts.committee_quorum_met,
        "committee_dissenting": facts.committee_dissenting,
        "verdict": facts.verdict,
        "action": facts.action,
        "risk": facts.risk,
        "expected_edge": facts.expected_edge,
        "simulation_only": facts.simulation_only,
        "requires_human_review": facts.requires_human_review,
        "has_outcome": facts.outcome is not None,
        "outcome_kind": facts.outcome.kind if facts.outcome else None,
    }
    return PipelineContext(
        pipeline_id=stable_hash({"lineage": facts.lineage_id, "kind": "pipeline"}),
        domain=facts.domain,
        candidate_id=facts.candidate_id,
        lineage_id=facts.lineage_id,
        initiated_at=facts.decided_at,
        initiator=facts.producer(),
        replay=False,
        metadata={"seed": seed, "advisory_only": ADVISORY_ONLY},
    )


def _stage_payload(kind: StageKind, seed: dict[str, Any], acc: dict[str, Any]) -> dict[str, Any]:
    if kind is StageKind.CONTEXT:
        return {"context_snapshot": {
            "domain": seed["domain"], "candidate_id": seed["candidate_id"],
            "strategy": seed["strategy"], "regime": seed["regime"],
            "decided_at": seed["decided_at"],
        }}
    if kind is StageKind.EVIDENCE:
        return {"evidence_bundle": {
            "sources": seed["evidence_sources"], "count": len(seed["evidence_sources"]),
            "evidence_weight": seed["evidence_weight"],
        }}
    if kind is StageKind.BAYESIAN:
        return {"posterior": seed["posterior"], "confidence": seed["confidence"],
                "prior": seed["prior"], "likelihood": seed["likelihood"]}
    if kind is StageKind.COMMITTEE:
        return {"committee_verdict": seed["committee_verdict"],
                "committee_confidence": seed["committee_confidence"],
                "quorum_met": seed["committee_quorum_met"],
                "dissenting": seed["committee_dissenting"]}
    if kind is StageKind.EXPLAINABILITY:
        return {"explanation_tree": {
            "final_decision": seed["verdict"], "final_action": seed["action"],
            "posterior": seed["posterior"], "top_sources": seed["evidence_sources"][:3],
        }}
    if kind is StageKind.PREVIEW:
        return {"preview_record": {
            "verdict": seed["verdict"], "action": seed["action"],
            "confidence": seed["confidence"], "risk": seed["risk"],
            "expected_edge": seed["expected_edge"],
            "simulation_only": seed["simulation_only"],
            "requires_human_review": seed["requires_human_review"],
            "advisory_only": ADVISORY_ONLY,
        }}
    if kind is StageKind.LEARNING:
        return {"learning_signal": {
            "kind": "EDGE_CONFIRMATION" if seed.get("outcome_kind") == "SUCCESS"
            else "OUTCOME_ANOMALY",
            "advisory_only": True,
        }}
    return {}


class AdvisoryDecisionPipeline(ScientificDecisionPipeline):
    """Records (never decides) a consumer decision as a canonical trace."""

    CONTRACT_VERSION = ScientificDecisionPipeline.CONTRACT_VERSION

    def __init__(self) -> None:
        self._traces: dict[str, PipelineTrace] = {}

    # ---- run -------------------------------------------------------------
    def run(self, context: PipelineContext) -> PipelineState:
        seed = dict(context.metadata.get("seed", {}))
        include_learning = bool(seed.get("has_outcome"))
        acc: dict[str, Any] = {"candidate_id": context.candidate_id, "domain": context.domain}
        outputs: dict[str, StageOutput] = {}
        stage_traces: list[StageTrace] = []

        for kind in STAGE_ORDER:
            if kind is StageKind.LEARNING and not include_learning:
                out = StageOutput(stage=kind, status=StageStatus.SKIPPED, payload={})
                outputs[kind.value] = out
                stage_traces.append(StageTrace(
                    stage=kind, status=StageStatus.SKIPPED,
                    input_hash=None, output_hash=None, duration_ms=None,
                ))
                continue

            contract = STAGE_CONTRACTS[kind]
            input_errors = contract.validate_input(acc)
            payload = _stage_payload(kind, seed, acc)
            output_errors = contract.validate_output(payload)
            errors = input_errors + output_errors
            status = StageStatus.PASSED if not errors else StageStatus.FAILED
            out = StageOutput(
                stage=kind, status=status, payload=payload,
                error="; ".join(errors) or None, duration_ms=None,
            )
            outputs[kind.value] = out
            acc.update(payload)
            stage_traces.append(StageTrace(
                stage=kind, status=status,
                input_hash=stable_hash(acc if input_errors else {k: acc.get(k) for k in contract.required_inputs}),
                output_hash=stable_hash(payload),
                duration_ms=None, error=out.error,
            ))

        failed = any(t.status == StageStatus.FAILED for t in stage_traces)
        final_status = PipelineStatus.FAILED if failed else PipelineStatus.COMPLETED
        state = PipelineState(
            context=context, status=final_status, current_stage=None,
            stage_outputs=outputs, errors=(),
            started_at=context.initiated_at, finished_at=context.initiated_at,
        )
        self._traces[context.pipeline_id] = PipelineTrace(
            pipeline_id=context.pipeline_id, context=context,
            final_status=final_status, stages=tuple(stage_traces),
            total_duration_ms=None, initiated_at=context.initiated_at,
            finished_at=context.initiated_at,
        )
        return state

    # ---- trace -----------------------------------------------------------
    def trace(self, pipeline_id: str) -> PipelineTrace | None:
        return self._traces.get(pipeline_id)

    # ---- replay ----------------------------------------------------------
    def replay(self, manifest: PipelineReplayManifest) -> PipelineState:
        # Deterministic reconstruction from the original immutable context.
        context = manifest.original_trace.context
        replay_ctx = PipelineContext(
            pipeline_id=context.pipeline_id, domain=context.domain,
            candidate_id=context.candidate_id, lineage_id=context.lineage_id,
            initiated_at=context.initiated_at, initiator=context.initiator,
            replay=True, metadata=context.metadata,
        )
        return self.run(replay_ctx)

    # ---- manifest --------------------------------------------------------
    def build_manifest(self, trace: PipelineTrace) -> PipelineReplayManifest:
        replay_inputs = tuple(
            ReplayInput(stage=st.stage, payload_hash=st.output_hash or "", evidence_refs=())
            for st in trace.stages if st.output_hash is not None
        )
        return PipelineReplayManifest(
            pipeline_id=trace.pipeline_id, original_trace=trace,
            replay_inputs=replay_inputs, created_at=trace.initiated_at,
        )
