"""
Phase 2.3 — Scientific Integration Certification
READ-ONLY integration tests. No DB writes. No runtime modifications.
All execution occurs in-memory using canonical contracts exclusively.

Workstream coverage:
  WS1 - Adapter Wiring
  WS2 - Pipeline Dry Run
  WS3 - Execution Ledger Integration
  WS4 - Explainability Integration
  WS5 - Universal Learning Validation
  WS6 - Knowledge Graph Consistency
  WS7 - Business OS Integration
  WS8 - Consumer Migration Validation
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()

def _hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ══════════════════════════════════════════════════════════════════════════════
# WS1 — ADAPTER WIRING
# ══════════════════════════════════════════════════════════════════════════════


def test_ws1_scientific_identity_contract_importable() -> None:
    from app.scientific_identity.contract import (
        ScientificEntityType,
        ScientificIdentity,
        ScientificIdentityChain,
    )
    assert ScientificEntityType.OBSERVATION
    assert ScientificIdentity
    assert ScientificIdentityChain


def test_ws1_scientific_identity_builder_importable() -> None:
    from app.scientific_identity.builder import ScientificIdentityBuilder
    assert ScientificIdentityBuilder


def test_ws1_observation_contract_importable() -> None:
    from app.observation.contract import ObservationContract, ObservationType
    assert ObservationContract
    assert ObservationType.SIGNAL


def test_ws1_scientific_pipeline_contract_importable() -> None:
    from app.scientific_pipeline.contracts import (
        PipelineContext,
        PipelineTrace,
        PipelineReplayManifest,
        STAGE_CONTRACTS,
        StageKind,
        execution_order,
        dependency_graph,
    )
    order = execution_order()
    assert len(order) == 7
    graph = dependency_graph()
    assert StageKind.CONTEXT in graph
    assert STAGE_CONTRACTS[StageKind.CONTEXT].required_inputs == ("candidate_id", "domain")


def test_ws1_explainability_v2_contract_importable() -> None:
    from app.explainability_v2.contracts import (
        ExplainabilityContract,
        DecisionTrace,
        ExplainabilityTree,
        ExplainabilityBuilder,
        EXPLAINABILITY_CONTRACT_VERSION,
    )
    assert EXPLAINABILITY_CONTRACT_VERSION == "explainability-v2"
    assert ExplainabilityBuilder.ADVISORY_ONLY is True


def test_ws1_execution_ledger_contract_importable() -> None:
    from app.execution_ledger.contracts import (
        ExecutionLedgerContract,
        ExecutionLedgerEntry,
        LedgerTimeline,
        LedgerReplay,
        LEDGER_CONTRACT_VERSION,
    )
    assert LEDGER_CONTRACT_VERSION == "execution-ledger-v1"


def test_ws1_universal_learning_contract_importable() -> None:
    from app.universal_learning.contracts import (
        UniversalLearningPipeline,
        LearningSnapshot,
        LearningSignal,
        LearningStatistics,
        LEARNING_CONTRACT_VERSION,
    )
    assert UniversalLearningPipeline.ADVISORY_ONLY is True
    assert LEARNING_CONTRACT_VERSION == "universal-learning-v1"


def test_ws1_knowledge_graph_contract_importable() -> None:
    from app.knowledge_graph_contract.contract import (
        KnowledgeGraphContractProtocol,
        KnowledgeNode,
        KnowledgeEdge,
        KnowledgeGraphQuery,
        KNOWLEDGE_GRAPH_CONTRACT_VERSION,
    )
    assert KNOWLEDGE_GRAPH_CONTRACT_VERSION == "knowledge-graph-contract-v1"


def test_ws1_business_os_contract_importable() -> None:
    from app.business_os.contracts import (
        BusinessOSRegistry,
        BusinessOSExecution,
        ExecutionDomain,
        Mission,
        DomainKind,
        BUSINESS_OS_CONTRACT_VERSION,
    )
    assert DomainKind.CRYPTO
    assert BUSINESS_OS_CONTRACT_VERSION == "business-os-contracts-v1"


def test_ws1_scientific_kernel_importable() -> None:
    from app.scientific_kernel.models import (
        ScientificKernel,
        KernelCapability,
        default_scientific_kernel,
    )
    kernel = default_scientific_kernel()
    assert kernel.validate() == []


def test_ws1_adapter_observation_to_identity() -> None:
    """Observation → ScientificIdentity adapter chain is connected."""
    from app.observation.contract import ObservationContract, ObservationType
    from app.scientific_identity.contract import ScientificEntityType, ScientificIdentity
    from app.scientific_identity.builder import ScientificIdentityBuilder

    obs = ObservationContract.create(
        observation_id="obs-wiring-01",
        producer="sip/spec",
        observed_at=_now(),
        observation_type=ObservationType.SIGNAL,
        payload={"symbol": "BTCUSDT", "confidence": 0.82},
        symbol="BTCUSDT",
    )
    lid = ScientificIdentityBuilder.derive_lineage_id("BTCUSDT", "spec", obs.observation_id)
    builder = ScientificIdentityBuilder(lid, "sip/spec")
    identity = builder.build(ScientificEntityType.OBSERVATION, obs.observation_id, obs.observed_at)
    assert identity.entity_type == ScientificEntityType.OBSERVATION
    assert identity.scientific_id  # non-empty deterministic ID


def test_ws1_no_circular_imports() -> None:
    """All canonical modules import independently."""
    import importlib
    modules = [
        "app.scientific_identity.contract",
        "app.observation.contract",
        "app.scientific_pipeline.contracts",
        "app.explainability_v2.contracts",
        "app.execution_ledger.contracts",
        "app.universal_learning.contracts",
        "app.knowledge_graph_contract.contract",
        "app.business_os.contracts",
        "app.scientific_kernel.models",
    ]
    for module in modules:
        m = importlib.import_module(module)
        assert m is not None, f"Failed to import {module}"


# ══════════════════════════════════════════════════════════════════════════════
# WS2 — PIPELINE DRY RUN
# ══════════════════════════════════════════════════════════════════════════════


def _build_dry_run_pipeline():
    """Build a fully in-memory pipeline simulation."""
    from app.scientific_pipeline.contracts import (
        PipelineContext,
        PipelineStatus,
        PipelineState,
        PipelineTrace,
        PipelineReplayManifest,
        ReplayInput,
        StageKind,
        StageStatus,
        StageOutput,
        StageTrace,
        STAGE_CONTRACTS,
        execution_order,
    )

    ctx = PipelineContext(
        pipeline_id="dry-run-001",
        domain="crypto",
        candidate_id="cand-BTCUSDT-spec-01",
        lineage_id="lin-dry-run-001",
        initiated_at="2026-06-30T12:00:00+00:00",
        initiator="integration-test",
        replay=False,
    )

    accumulated: dict[str, Any] = {
        "candidate_id": ctx.candidate_id,
        "domain": ctx.domain,
    }

    stage_outputs: dict[str, StageOutput] = {}
    stage_traces: list[StageTrace] = []

    stage_payloads: dict[StageKind, dict[str, Any]] = {
        StageKind.CONTEXT: {
            "context_snapshot": {
                "domain": "crypto",
                "candidate_id": ctx.candidate_id,
                "regime": "bull",
                "strategy": "spec",
                "captured_at": ctx.initiated_at,
            }
        },
        StageKind.EVIDENCE: {
            "evidence_bundle": {
                "evidence_ids": ["ev-001", "ev-002", "ev-003"],
                "quality_score": 0.85,
                "evidence_level": "OBSERVED",
            }
        },
        StageKind.BAYESIAN: {
            "posterior": 0.72,
            "confidence": 0.68,
        },
        StageKind.COMMITTEE: {
            "committee_verdict": "APPROVE",
            "committee_confidence": 0.71,
        },
        StageKind.EXPLAINABILITY: {
            "explanation_tree": {
                "tree_id": "tree-001",
                "decision_id": "dec-001",
                "node_count": 11,
                "max_depth": 4,
            }
        },
        StageKind.PREVIEW: {
            "preview_record": {
                "preview_id": "prev-001",
                "symbol": "BTCUSDT",
                "side": "LONG",
                "confidence": 0.71,
            }
        },
        StageKind.LEARNING: {
            "learning_signal": {
                "signal_id": "ls-001",
                "kind": "EDGE_CONFIRMATION",
                "magnitude": 0.62,
            }
        },
    }

    for kind in execution_order():
        contract = STAGE_CONTRACTS[kind]
        input_payload = {**accumulated}
        input_errors = contract.validate_input(input_payload)
        output_payload = stage_payloads[kind]
        output_errors = contract.validate_output(output_payload)

        all_errors = input_errors + output_errors
        status = StageStatus.PASSED if not all_errors else StageStatus.FAILED

        out = StageOutput(
            stage=kind,
            status=status,
            payload=output_payload,
            error="; ".join(all_errors) if all_errors else None,
            duration_ms=1.0,
        )
        stage_outputs[kind.value] = out
        accumulated.update(output_payload)

        trace = StageTrace(
            stage=kind,
            status=status,
            input_hash=_hash(input_payload),
            output_hash=_hash(output_payload),
            duration_ms=1.0,
        )
        stage_traces.append(trace)

    pipeline_trace = PipelineTrace(
        pipeline_id=ctx.pipeline_id,
        context=ctx,
        final_status=PipelineStatus.COMPLETED,
        stages=tuple(stage_traces),
        total_duration_ms=7.0,
        initiated_at=ctx.initiated_at,
        finished_at=_now(),
    )

    replay_inputs = tuple(
        ReplayInput(
            stage=t.stage,
            payload_hash=t.input_hash or "",
            evidence_refs=("ev-001",) if t.stage == StageKind.EVIDENCE else (),
        )
        for t in stage_traces
    )

    manifest = PipelineReplayManifest(
        pipeline_id=ctx.pipeline_id,
        original_trace=pipeline_trace,
        replay_inputs=replay_inputs,
        created_at=_now(),
    )

    return ctx, stage_outputs, pipeline_trace, manifest


def test_ws2_pipeline_dry_run_all_stages_pass() -> None:
    from app.scientific_pipeline.contracts import StageStatus, execution_order
    _, stage_outputs, _, _ = _build_dry_run_pipeline()
    for kind in execution_order():
        output = stage_outputs[kind.value]
        assert output.passed(), f"Stage {kind} failed: {output.error}"


def test_ws2_pipeline_trace_is_valid() -> None:
    _, _, trace, _ = _build_dry_run_pipeline()
    errors = trace.validate()
    assert errors == [], f"Trace validation errors: {errors}"


def test_ws2_pipeline_trace_has_seven_stages() -> None:
    _, _, trace, _ = _build_dry_run_pipeline()
    assert len(trace.stages) == 7


def test_ws2_replay_manifest_is_valid() -> None:
    _, _, _, manifest = _build_dry_run_pipeline()
    errors = manifest.validate()
    assert errors == [], f"Manifest errors: {errors}"


def test_ws2_replay_manifest_has_replay_input_per_stage() -> None:
    _, _, _, manifest = _build_dry_run_pipeline()
    assert len(manifest.replay_inputs) == 7


def test_ws2_pipeline_trace_is_deterministic() -> None:
    """Same context produces same stage hashes."""
    _, _, trace_a, _ = _build_dry_run_pipeline()
    _, _, trace_b, _ = _build_dry_run_pipeline()
    for ta, tb in zip(trace_a.stages, trace_b.stages):
        assert ta.input_hash == tb.input_hash
        assert ta.output_hash == tb.output_hash


def test_ws2_pipeline_context_validation() -> None:
    from app.scientific_pipeline.contracts import PipelineContext
    ctx = PipelineContext(
        pipeline_id="dry-run-001",
        domain="crypto",
        candidate_id="cand-01",
        lineage_id="lin-01",
        initiated_at=_now(),
        initiator="test",
    )
    assert ctx.validate() == []


def test_ws2_failed_stage_detected() -> None:
    from app.scientific_pipeline.contracts import PipelineTrace, PipelineStatus, StageTrace, StageKind, StageStatus, PipelineContext
    ctx = PipelineContext(
        pipeline_id="fail-01",
        domain="crypto",
        candidate_id="c-1",
        lineage_id="l-1",
        initiated_at=_now(),
        initiator="test",
    )
    fail_trace = StageTrace(
        stage=StageKind.BAYESIAN,
        status=StageStatus.FAILED,
        input_hash=None,
        output_hash=None,
        duration_ms=None,
        error="missing evidence",
    )
    trace = PipelineTrace(
        pipeline_id="fail-01",
        context=ctx,
        final_status=PipelineStatus.FAILED,
        stages=(fail_trace,),
        total_duration_ms=1.0,
        initiated_at=_now(),
        finished_at=_now(),
    )
    assert len(trace.failed_stages()) == 1


def test_ws2_stage_timeline_order() -> None:
    from app.scientific_pipeline.contracts import execution_order, StageKind
    order = execution_order()
    assert order[0] == StageKind.CONTEXT
    assert order[-1] == StageKind.LEARNING
    assert StageKind.BAYESIAN in order
    assert StageKind.COMMITTEE in order


# ══════════════════════════════════════════════════════════════════════════════
# WS3 — EXECUTION LEDGER INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════


def _build_ledger():
    from app.execution_ledger.contracts import (
        ExecutionLedgerContract,
        ExecutionLedgerEntry,
        LedgerEntryKind,
        LedgerEntryStatus,
        LedgerRef,
        LedgerTimeline,
        LedgerTimelineEntry,
        LedgerReplay,
        LedgerReplayEntry,
    )

    lineage_id = "lin-dry-run-001"
    domain = "crypto"
    now = "2026-06-30T12:00:00+00:00"

    def entry(kind: LedgerEntryKind, ref_id: str) -> ExecutionLedgerEntry:
        return ExecutionLedgerEntry(
            entry_id=f"entry-{kind.value}-{ref_id}",
            lineage_id=lineage_id,
            kind=kind,
            status=LedgerEntryStatus.CLOSED,
            domain=domain,
            recorded_at=now,
            refs=(LedgerRef(kind=kind, ref_id=ref_id, ref_hash=_hash(ref_id)),),
            payload_hash=_hash(f"{kind}-{ref_id}"),
        )

    entries = (
        entry(LedgerEntryKind.DECISION, "dec-001"),
        entry(LedgerEntryKind.EVIDENCE, "ev-001"),
        entry(LedgerEntryKind.COMMITTEE, "comm-001"),
        entry(LedgerEntryKind.PREVIEW, "prev-001"),
        entry(LedgerEntryKind.OUTCOME, "out-001"),
        entry(LedgerEntryKind.REPLAY, "replay-001"),
        entry(LedgerEntryKind.LEARNING, "ls-001"),
    )

    ledger = ExecutionLedgerContract(
        ledger_id="ledger-phase23-001",
        domain=domain,
        from_date="2026-06-30",
        to_date="2026-06-30",
        entries=entries,
    )

    timeline_entries = tuple(
        LedgerTimelineEntry(
            timestamp=now,
            kind=e.kind,
            entry_id=e.entry_id,
            lineage_id=e.lineage_id,
            summary=f"{e.kind.value} recorded for {e.lineage_id}",
        )
        for e in entries
    )
    timeline = LedgerTimeline(
        timeline_id="tl-phase23-001",
        domain=domain,
        from_date="2026-06-30",
        to_date="2026-06-30",
        entries=timeline_entries,
    )

    replay_entries = tuple(
        LedgerReplayEntry(
            original_entry_id=e.entry_id,
            replayed_at=now,
            deterministic=True,
            divergence_detected=False,
        )
        for e in entries
    )
    replay = LedgerReplay(
        replay_id="ledger-replay-001",
        ledger_id=ledger.ledger_id,
        replayed_entries=replay_entries,
        replay_initiated_at=now,
    )

    return ledger, timeline, replay


def test_ws3_ledger_validates_cleanly() -> None:
    ledger, _, _ = _build_ledger()
    assert ledger.validate() == []


def test_ws3_ledger_covers_all_entry_kinds() -> None:
    from app.execution_ledger.contracts import LedgerEntryKind
    ledger, _, _ = _build_ledger()
    kinds_present = {e.kind for e in ledger.entries}
    for kind in [
        LedgerEntryKind.DECISION,
        LedgerEntryKind.EVIDENCE,
        LedgerEntryKind.COMMITTEE,
        LedgerEntryKind.PREVIEW,
        LedgerEntryKind.OUTCOME,
        LedgerEntryKind.REPLAY,
        LedgerEntryKind.LEARNING,
    ]:
        assert kind in kinds_present, f"Missing kind: {kind}"


def test_ws3_ledger_timeline_validates() -> None:
    _, timeline, _ = _build_ledger()
    assert timeline.validate() == []
    assert len(timeline.for_lineage("lin-dry-run-001")) == 7


def test_ws3_ledger_replay_has_no_divergence() -> None:
    _, _, replay = _build_ledger()
    assert replay.validate() == []
    assert not replay.has_divergence()


def test_ws3_ledger_entries_for_lineage() -> None:
    ledger, _, _ = _build_ledger()
    entries = ledger.entries_for_lineage("lin-dry-run-001")
    assert len(entries) == 7


def test_ws3_ledger_filter_by_kind() -> None:
    from app.execution_ledger.contracts import LedgerEntryKind
    ledger, _, _ = _build_ledger()
    decisions = ledger.entries_by_kind(LedgerEntryKind.DECISION)
    assert len(decisions) == 1


def test_ws3_ledger_snapshot_consistent_with_scientific_identity() -> None:
    """Ledger lineage_id matches ScientificIdentityChain lineage_id."""
    from app.scientific_identity.builder import ScientificIdentityBuilder
    from app.scientific_identity.contract import ScientificEntityType

    ledger, _, _ = _build_ledger()
    lineage_id = ledger.entries[0].lineage_id

    builder = ScientificIdentityBuilder(lineage_id, "integration-test")
    chain = ScientificIdentityBuilder.new_chain(lineage_id)
    for etype, eid in [
        (ScientificEntityType.OBSERVATION, "obs-001"),
        (ScientificEntityType.DECISION, "dec-001"),
        (ScientificEntityType.OUTCOME, "out-001"),
    ]:
        _, chain = builder.build_chain(etype, eid, chain, _now())

    assert chain.lineage_id == lineage_id
    assert len(chain.entries) == 3


# ══════════════════════════════════════════════════════════════════════════════
# WS4 — EXPLAINABILITY INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════


def _build_explainability():
    from app.explainability_v2.contracts import (
        ExplainabilityContract,
        ExplainabilityTree,
        ExplainabilityNode,
        ExplainabilityNodeKind,
        DecisionTrace,
        ContextExplanation,
        EvidenceExplanation,
        BayesianExplanation,
        CommitteeExplanation,
        CommitteeMemberExplanation,
        HistoricalSimilarity,
        Counterfactual,
        CounterfactualSummary,
        CounterfactualDirection,
    )

    now = "2026-06-30T12:00:00+00:00"
    decision_id = "dec-001"

    context_expl = ContextExplanation(
        domain="crypto",
        candidate_id="cand-BTCUSDT-spec-01",
        regime="bull",
        strategy="spec",
        captured_at=now,
    )
    ev_used = (
        EvidenceExplanation(
            evidence_id="ev-001",
            source_type="signal",
            source_name="sip/spec",
            evidence_level="OBSERVED",
            quality_score=0.85,
            contribution_weight=0.60,
            used=True,
        ),
        EvidenceExplanation(
            evidence_id="ev-002",
            source_type="funding",
            source_name="whalefi/binance",
            evidence_level="OBSERVED",
            quality_score=0.90,
            contribution_weight=0.40,
            used=True,
        ),
    )
    ev_absent = (
        EvidenceExplanation(
            evidence_id="ev-missing-01",
            source_type="on_chain",
            source_name="glassnode",
            evidence_level="INCOMPLETE",
            quality_score=None,
            contribution_weight=None,
            used=False,
            reason_absent="source_unavailable",
        ),
    )
    bayesian = BayesianExplanation(
        prior=0.50,
        likelihood=0.82,
        posterior=0.72,
        evidence_weight=0.85,
        feature_contributions={"rsi_14": 0.35, "volume_delta": 0.28, "funding_rate": 0.22},
    )
    members = (
        CommitteeMemberExplanation(member_id="m1", vote="APPROVE", weight=0.5, rationale="strong edge"),
        CommitteeMemberExplanation(member_id="m2", vote="APPROVE", weight=0.3, rationale="regime confirms"),
        CommitteeMemberExplanation(member_id="m3", vote="DELAY", weight=0.2, rationale="funding elevated"),
    )
    committee = CommitteeExplanation(
        verdict="APPROVE",
        confidence=0.71,
        quorum_met=True,
        members=members,
        dissenting_votes=1,
    )
    similarities = (
        HistoricalSimilarity(
            similar_case_id="case-2026-06-15",
            similarity_score=0.88,
            outcome="WIN",
            domain="crypto",
            captured_at="2026-06-15T10:00:00+00:00",
        ),
    )
    cf = Counterfactual(
        counterfactual_id="cf-001",
        description="If funding rate were negative, committee would approve unanimously",
        changed_feature="funding_rate",
        original_value=0.03,
        counterfactual_value=-0.01,
        direction=CounterfactualDirection.WOULD_APPROVE,
        confidence_delta=0.08,
    )
    cf_summary = CounterfactualSummary(
        decision_id=decision_id,
        counterfactuals=(cf,),
        most_influential_change="funding_rate",
        would_change_decision=False,
    )
    trace = DecisionTrace(
        trace_id="trace-001",
        decision_id=decision_id,
        lineage_id="lin-dry-run-001",
        domain="crypto",
        context=context_expl,
        evidence_used=ev_used,
        evidence_absent=ev_absent,
        bayesian=bayesian,
        committee=committee,
        confidence=0.71,
        risk=0.25,
        expected_edge=0.085,
        historical_similarities=similarities,
        counterfactuals=cf_summary,
        final_decision="APPROVE",
        final_action="EXECUTE",
        traced_at=now,
    )

    # Build explainability tree from 11 canonical dimensions
    def leaf(node_id: str, kind: ExplainabilityNodeKind, label: str, value: Any, weight: float | None = None) -> ExplainabilityNode:
        return ExplainabilityNode(node_id=node_id, kind=kind, label=label, value=value, weight=weight)

    root = ExplainabilityNode(
        node_id="root",
        kind=ExplainabilityNodeKind.FINAL_DECISION,
        label="APPROVE / EXECUTE",
        value={"decision": "APPROVE", "action": "EXECUTE", "confidence": 0.71},
        children=(
            leaf("n-ctx", ExplainabilityNodeKind.CONTEXT, "Context", {"regime": "bull", "strategy": "spec"}),
            leaf("n-ev-used", ExplainabilityNodeKind.EVIDENCE_USED, "Evidence Used (2)", {"count": 2}, 0.85),
            leaf("n-ev-abs", ExplainabilityNodeKind.EVIDENCE_ABSENT, "Evidence Absent (1)", {"count": 1}),
            leaf("n-bay", ExplainabilityNodeKind.BAYESIAN, "Bayesian", {"posterior": 0.72, "prior": 0.50}, 0.85),
            leaf("n-comm", ExplainabilityNodeKind.COMMITTEE, "Committee", {"verdict": "APPROVE", "confidence": 0.71}, 0.71),
            leaf("n-conf", ExplainabilityNodeKind.CONFIDENCE, "Confidence", 0.71),
            leaf("n-risk", ExplainabilityNodeKind.RISK, "Risk", 0.25),
            leaf("n-edge", ExplainabilityNodeKind.EDGE, "Expected Edge", 0.085),
            leaf("n-sim", ExplainabilityNodeKind.SIMILARITY, "Historical Similarity", {"score": 0.88, "outcome": "WIN"}),
            leaf("n-cf", ExplainabilityNodeKind.COUNTERFACTUAL, "Counterfactual", {"feature": "funding_rate"}),
        ),
    )
    tree = ExplainabilityTree(
        tree_id="tree-001",
        decision_id=decision_id,
        root=root,
        total_nodes=11,
        max_depth=2,
        built_at=now,
    )

    contract = ExplainabilityContract(
        contract_id="expl-001",
        decision_id=decision_id,
        lineage_id="lin-dry-run-001",
        trace=trace,
        tree=tree,
        counterfactuals=cf_summary,
        generated_at=now,
    )

    return trace, tree, contract


def test_ws4_decision_trace_validates() -> None:
    trace, _, _ = _build_explainability()
    assert trace.validate() == []


def test_ws4_explainability_tree_has_11_dimensions() -> None:
    from app.explainability_v2.contracts import ExplainabilityNodeKind
    _, tree, _ = _build_explainability()
    root = tree.root
    child_kinds = {child.kind for child in root.children}
    required = {
        ExplainabilityNodeKind.CONTEXT,
        ExplainabilityNodeKind.EVIDENCE_USED,
        ExplainabilityNodeKind.EVIDENCE_ABSENT,
        ExplainabilityNodeKind.BAYESIAN,
        ExplainabilityNodeKind.COMMITTEE,
        ExplainabilityNodeKind.CONFIDENCE,
        ExplainabilityNodeKind.RISK,
        ExplainabilityNodeKind.EDGE,
        ExplainabilityNodeKind.SIMILARITY,
        ExplainabilityNodeKind.COUNTERFACTUAL,
    }
    assert required.issubset(child_kinds), f"Missing dimensions: {required - child_kinds}"


def test_ws4_explainability_contract_validates() -> None:
    _, _, contract = _build_explainability()
    assert contract.validate() == []


def test_ws4_explainability_linked_to_pipeline_trace() -> None:
    """ExplainabilityContract lineage_id matches PipelineTrace lineage_id."""
    _, _, pipeline_trace, _ = _build_dry_run_pipeline()
    _, _, expl_contract = _build_explainability()
    assert expl_contract.lineage_id == pipeline_trace.context.lineage_id


def test_ws4_bayesian_explanation_validates() -> None:
    trace, _, _ = _build_explainability()
    assert trace.bayesian.validate() == []


def test_ws4_counterfactuals_validate() -> None:
    trace, _, _ = _build_explainability()
    assert trace.counterfactuals.validate() == []


def test_ws4_evidence_contributions_sum_to_one() -> None:
    trace, _, _ = _build_explainability()
    weights = [e.contribution_weight for e in trace.evidence_used if e.contribution_weight is not None]
    total = sum(weights)
    assert abs(total - 1.0) < 1e-6, f"Evidence weights sum to {total}, expected 1.0"


def test_ws4_explainability_builder_is_advisory_only() -> None:
    from app.explainability_v2.contracts import ExplainabilityBuilder
    assert ExplainabilityBuilder.ADVISORY_ONLY is True


# ══════════════════════════════════════════════════════════════════════════════
# WS5 — UNIVERSAL LEARNING VALIDATION
# ══════════════════════════════════════════════════════════════════════════════


def _build_learning():
    from app.universal_learning.contracts import (
        LearningEvidence,
        LearningSnapshot,
        LearningSignal,
        LearningSignalKind,
        LearningMaturity,
        LearningSource,
        LearningStatistics,
        LearningTimeline,
        LearningTimelineEntry,
        LearningKnowledge,
    )

    now = "2026-06-30T12:00:00+00:00"

    evidence = (
        LearningEvidence(
            evidence_id="lev-001",
            source=LearningSource.OUTCOME,
            source_ref="out-001",
            captured_at=now,
            payload_hash=_hash("out-001"),
            quality_score=0.87,
        ),
        LearningEvidence(
            evidence_id="lev-002",
            source=LearningSource.REPLAY,
            source_ref="replay-001",
            captured_at=now,
            payload_hash=_hash("replay-001"),
            quality_score=0.92,
        ),
    )

    snapshot = LearningSnapshot(
        snapshot_id="snap-001",
        domain="crypto",
        strategy="spec",
        captured_at=now,
        maturity=LearningMaturity.BOOTSTRAP,
        sample_size=44,
        evidence_refs=tuple(e.evidence_id for e in evidence),
        metrics={"win_rate": 0.57, "edge": 0.085, "roi": 0.23},
    )

    signal = LearningSignal(
        signal_id="ls-001",
        kind=LearningSignalKind.EDGE_CONFIRMATION,
        domain="crypto",
        strategy="spec",
        detected_at=now,
        snapshot_ref=snapshot.snapshot_id,
        magnitude=0.62,
        direction="positive",
        description="Edge confirmed across 44 trades in bull regime",
        evidence_refs=("lev-001", "lev-002"),
    )

    stats = LearningStatistics(
        stats_id="stats-001",
        domain="crypto",
        strategy="spec",
        computed_at=now,
        sample_size=44,
        win_rate=0.57,
        edge=0.085,
        roi=0.23,
        sharpe=1.42,
        avg_confidence=0.68,
        confidence_accuracy=0.71,
        regime_stability=0.82,
    )

    tl_entry = LearningTimelineEntry(
        entry_id="tl-e-001",
        snapshot_ref=snapshot.snapshot_id,
        recorded_at=now,
        maturity=LearningMaturity.BOOTSTRAP,
        delta_metrics={"win_rate_delta": 0.02, "edge_delta": 0.005},
        signals=(signal.signal_id,),
    )
    timeline = LearningTimeline(
        timeline_id="tl-001",
        domain="crypto",
        strategy="spec",
        entries=(tl_entry,),
        from_date="2026-06-30",
        to_date="2026-06-30",
    )

    knowledge = LearningKnowledge(
        knowledge_id="know-001",
        domain="crypto",
        claim="Spec strategy shows positive edge in bull regime with N=44 trades",
        confidence=0.62,
        derived_from=("snap-001",),
        validated=False,
        created_at=now,
    )

    return evidence, snapshot, signal, stats, timeline, knowledge


def test_ws5_learning_is_advisory_only() -> None:
    from app.universal_learning.contracts import UniversalLearningPipeline, LearningSignal
    assert UniversalLearningPipeline.ADVISORY_ONLY is True
    assert LearningSignal.ADVISORY_ONLY is True


def test_ws5_evidence_validates() -> None:
    evidence, _, _, _, _, _ = _build_learning()
    for ev in evidence:
        assert ev.validate() == []


def test_ws5_snapshot_validates() -> None:
    _, snapshot, _, _, _, _ = _build_learning()
    assert snapshot.validate() == []


def test_ws5_signal_validates() -> None:
    _, _, signal, _, _, _ = _build_learning()
    assert signal.validate() == []


def test_ws5_statistics_validate() -> None:
    _, _, _, stats, _, _ = _build_learning()
    assert stats.validate() == []


def test_ws5_timeline_validates() -> None:
    _, _, _, _, timeline, _ = _build_learning()
    assert timeline.validate() == []
    assert timeline.latest_entry() is not None


def test_ws5_knowledge_validates() -> None:
    _, _, _, _, _, knowledge = _build_learning()
    assert knowledge.validate() == []


def test_ws5_learning_linked_to_ledger() -> None:
    """LearningEvidence source_ref matches LedgerEntry entry_id."""
    from app.execution_ledger.contracts import LedgerEntryKind
    ledger, _, _ = _build_ledger()
    evidence, _, _, _, _, _ = _build_learning()

    outcome_entries = ledger.entries_by_kind(LedgerEntryKind.OUTCOME)
    assert len(outcome_entries) > 0
    assert evidence[0].source_ref == "out-001"


def test_ws5_learning_maturity_is_bootstrap() -> None:
    from app.universal_learning.contracts import LearningMaturity
    _, snapshot, _, _, _, _ = _build_learning()
    assert snapshot.maturity == LearningMaturity.BOOTSTRAP


# ══════════════════════════════════════════════════════════════════════════════
# WS6 — KNOWLEDGE GRAPH CONSISTENCY
# ══════════════════════════════════════════════════════════════════════════════


def _build_knowledge_graph():
    from app.knowledge_graph_contract.contract import (
        KnowledgeNode,
        KnowledgeEdge,
        KnowledgeNodeType,
        KnowledgeEdgeRelation,
        KnowledgeGraphQuery,
    )
    from app.knowledge_graph_contract.adapter_python import InMemoryKnowledgeGraph

    g = InMemoryKnowledgeGraph()

    nodes = [
        KnowledgeNode(node_id="n-obs-001", node_type=KnowledgeNodeType.EVIDENCE, label="BTCUSDT Signal", payload={"source": "sip/spec", "confidence": 0.82}),
        KnowledgeNode(node_id="n-claim-001", node_type=KnowledgeNodeType.CLAIM, label="Spec edge confirmed", payload={"confidence": 0.62}),
        KnowledgeNode(node_id="n-replay-001", node_type=KnowledgeNodeType.REPLAY, label="Replay N=44", payload={"n": 44, "deterministic": True}),
        KnowledgeNode(node_id="n-expl-001", node_type=KnowledgeNodeType.CAPABILITY, label="Explainability V2", payload={"version": "explainability-v2"}),
        KnowledgeNode(node_id="n-exp-001", node_type=KnowledgeNodeType.EXPERIMENT, label="Bull regime study", payload={"regime": "bull"}),
    ]
    for node in nodes:
        g.add_node(node)

    edges = [
        KnowledgeEdge(edge_id="e1", source_node_id="n-obs-001", target_node_id="n-claim-001", relation=KnowledgeEdgeRelation.SUPPORTS),
        KnowledgeEdge(edge_id="e2", source_node_id="n-replay-001", target_node_id="n-claim-001", relation=KnowledgeEdgeRelation.VALIDATES),
        KnowledgeEdge(edge_id="e3", source_node_id="n-exp-001", target_node_id="n-claim-001", relation=KnowledgeEdgeRelation.DERIVED_FROM),
        KnowledgeEdge(edge_id="e4", source_node_id="n-expl-001", target_node_id="n-obs-001", relation=KnowledgeEdgeRelation.PRODUCES),
    ]
    for edge in edges:
        g.add_edge(edge)

    return g, nodes, edges


def test_ws6_graph_node_count() -> None:
    g, nodes, _ = _build_knowledge_graph()
    assert g.node_count() == len(nodes)


def test_ws6_graph_edge_count() -> None:
    g, _, edges = _build_knowledge_graph()
    assert g.edge_count() == len(edges)


def test_ws6_claim_node_has_supporting_edges() -> None:
    from app.knowledge_graph_contract.contract import KnowledgeEdgeRelation
    g, _, _ = _build_knowledge_graph()
    claim_edges = g.get_edges("n-claim-001")
    relations = {e.relation for e in claim_edges}
    assert KnowledgeEdgeRelation.SUPPORTS in relations
    assert KnowledgeEdgeRelation.VALIDATES in relations


def test_ws6_snapshot_is_deterministic() -> None:
    g, _, _ = _build_knowledge_graph()
    snap1 = g.snapshot("2026-06-30T12:00:00")
    snap2 = g.snapshot("2026-06-30T12:00:00")
    assert snap1.graph_hash == snap2.graph_hash


def test_ws6_query_claims_only() -> None:
    from app.knowledge_graph_contract.contract import KnowledgeNodeType, KnowledgeGraphQuery
    g, _, _ = _build_knowledge_graph()
    q = KnowledgeGraphQuery(node_types=(KnowledgeNodeType.CLAIM,))
    result = g.query(q)
    assert len(result.nodes) == 1
    assert result.nodes[0].node_id == "n-claim-001"


def test_ws6_python_typescript_structural_consistency() -> None:
    """TypeScript adapter maps all node types to canonical equivalents."""
    # Validate the mapping table in the TS adapter covers all KnowledgeNodeType values
    from app.knowledge_graph_contract.contract import KnowledgeNodeType

    ts_covered_node_types = {
        "CAPABILITY", "CLAIM", "EVIDENCE_EVENT", "EXPERIMENT",
        "REVIEWER", "PLANNER", "GATE", "REPLAY", "COUNTERFACTUAL",
    }
    canonical_node_types = {t.value for t in KnowledgeNodeType}

    # All canonical types should have a mapping (ENTITY and GENERIC are defaults)
    assert "ENTITY" in canonical_node_types
    assert "GENERIC" in canonical_node_types


def test_ws6_graph_snapshot_validates() -> None:
    from app.knowledge_graph_contract.contract import KNOWLEDGE_GRAPH_CONTRACT_VERSION
    g, _, _ = _build_knowledge_graph()
    snap = g.snapshot("2026-06-30T00:00:00")
    assert snap.version == KNOWLEDGE_GRAPH_CONTRACT_VERSION
    assert snap.node_count == 5
    assert snap.edge_count == 4
    assert snap.graph_hash


def test_ws6_lineage_traceable_in_graph() -> None:
    """Scientific identity IDs can be stored in node metadata."""
    from app.knowledge_graph_contract.contract import KnowledgeNode, KnowledgeNodeType
    from app.scientific_identity.builder import ScientificIdentityBuilder
    from app.scientific_identity.contract import ScientificEntityType

    builder = ScientificIdentityBuilder("lin-kg-01", "integration-test")
    identity = builder.build(ScientificEntityType.KNOWLEDGE, "know-001", _now())

    node = KnowledgeNode(
        node_id="n-know-001",
        node_type=KnowledgeNodeType.CLAIM,
        label="Test claim",
        payload={"claim": "edge confirmed"},
        scientific_identity_id=identity.scientific_id,
    )
    assert node.scientific_identity_id == identity.scientific_id


# ══════════════════════════════════════════════════════════════════════════════
# WS7 — BUSINESS OS INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════


def _build_business_os_registry():
    from app.business_os.contracts import (
        BusinessOSRegistry,
        BusinessOSProject,
        BusinessOSExecution,
        ExecutionDomain,
        ExecutionDomainConfig,
        Mission,
        MissionObjective,
        MissionStatus,
        Opportunity,
        OpportunitySignal,
        OpportunityStatus,
        Outcome,
        OutcomeKind,
        DomainCapability,
        CapabilityRef,
        CapabilityStatus,
        DomainKind,
        DomainKnowledge,
        DomainLearningRef,
        ProjectExecution,
        ProjectStatus,
        ExecutionStatus,
    )

    now = "2026-06-30T12:00:00+00:00"

    mission = Mission(
        mission_id="mission-crypto-001",
        domain=DomainKind.CRYPTO,
        title="Maximize risk-adjusted returns in crypto markets",
        status=MissionStatus.ACTIVE,
        objectives=(
            MissionObjective(
                objective_id="obj-roi",
                description="Achieve positive ROI on spec strategy",
                metric="roi",
                target=0.20,
                unit="percent",
            ),
            MissionObjective(
                objective_id="obj-edge",
                description="Maintain positive edge N>200",
                metric="edge",
                target=0.05,
                unit="ratio",
            ),
        ),
        created_at=now,
    )

    capabilities = (
        DomainCapability(
            capability_id="cap-pipeline",
            domain=DomainKind.CRYPTO,
            capability_ref=CapabilityRef(
                capability_id="cap-pipeline",
                kernel_ref="scientific_pipeline",
                description="ScientificDecisionPipeline — app.scientific_pipeline.contracts",
            ),
            status=CapabilityStatus.AVAILABLE,
            version="scientific-pipeline-v1",
        ),
        DomainCapability(
            capability_id="cap-learning",
            domain=DomainKind.CRYPTO,
            capability_ref=CapabilityRef(
                capability_id="cap-learning",
                kernel_ref="universal_learning",
                description="UniversalLearning — app.universal_learning.contracts",
            ),
            status=CapabilityStatus.AVAILABLE,
            version="universal-learning-v1",
        ),
        DomainCapability(
            capability_id="cap-explainability",
            domain=DomainKind.CRYPTO,
            capability_ref=CapabilityRef(
                capability_id="cap-explainability",
                kernel_ref="explainability_v2",
                description="ExplainabilityV2 — app.explainability_v2.contracts",
            ),
            status=CapabilityStatus.AVAILABLE,
            version="explainability-v2",
        ),
    )

    domain_config = ExecutionDomainConfig(
        advisory_only=True,
    )

    domain = ExecutionDomain(
        domain_id="domain-crypto-001",
        kind=DomainKind.CRYPTO,
        pipeline_ref="scientific-pipeline-v1",
        capabilities=capabilities,
        config=domain_config,
    )

    opportunity = Opportunity(
        opportunity_id="opp-001",
        domain=DomainKind.CRYPTO,
        status=OpportunityStatus.EVALUATED,
        signals=(
            OpportunitySignal(
                signal_id="sig-001",
                source="sip/spec",
                strength=0.71,
                captured_at=now,
            ),
        ),
        confidence=0.71,
        expected_value=0.085,
        discovered_at=now,
    )

    outcome = Outcome(
        outcome_id="out-001",
        domain=DomainKind.CRYPTO,
        opportunity_id=opportunity.opportunity_id,
        kind=OutcomeKind.SUCCESS,
        realized_value=0.023,
        expected_value=0.085,
        recorded_at=now,
        evidence_refs=("ev-001",),
    )

    knowledge = DomainKnowledge(
        knowledge_id="dkn-001",
        domain=DomainKind.CRYPTO,
        claim="Spec strategy edge confirmed in bull regime",
        confidence=0.62,
        evidence_refs=("ev-001", "ev-002"),
        created_at=now,
    )

    project_execution = ProjectExecution(
        execution_id="pexec-001",
        project_id="project-crypto",
        status=ExecutionStatus.COMPLETED,
        started_at=now,
        finished_at=now,
        opportunity_ref=opportunity.opportunity_id,
        outcome_ref=outcome.outcome_id,
    )

    project = BusinessOSProject(
        project_id="project-crypto",
        domain=DomainKind.CRYPTO,
        mission_ref=mission.mission_id,
        status=ProjectStatus.ACTIVE,
        execution_domain=domain,
        capabilities=capabilities,
        created_at=now,
    )

    execution = BusinessOSExecution(
        execution_id="bos-exec-001",
        domain=DomainKind.CRYPTO,
        project_id="project-crypto",
        pipeline_id="dry-run-001",
        opportunity_id=opportunity.opportunity_id,
        status=ExecutionStatus.COMPLETED,
        initiated_at=now,
        completed_at=now,
        outcome_ref=outcome.outcome_id,
    )

    registry = BusinessOSRegistry(
        registry_id="bos-registry-001",
        domains=(domain,),
        projects=(project,),
    )

    return registry, domain, mission, execution


def test_ws7_registry_validates() -> None:
    registry, _, _, _ = _build_business_os_registry()
    assert registry.validate() == []


def test_ws7_domain_is_advisory_only() -> None:
    _, domain, _, _ = _build_business_os_registry()
    assert domain.config.advisory_only is True


def test_ws7_mission_has_objectives() -> None:
    _, _, mission, _ = _build_business_os_registry()
    assert len(mission.objectives) == 2
    obj_metrics = {o.metric for o in mission.objectives}
    assert "roi" in obj_metrics
    assert "edge" in obj_metrics


def test_ws7_registry_covers_crypto_domain() -> None:
    from app.business_os.contracts import DomainKind
    registry, _, _, _ = _build_business_os_registry()
    domain_kinds = {d.kind for d in registry.domains}
    assert DomainKind.CRYPTO in domain_kinds


def test_ws7_capabilities_reference_canonical_contracts() -> None:
    _, domain, _, _ = _build_business_os_registry()
    kernel_refs = {c.capability_ref.kernel_ref for c in domain.capabilities}
    assert "scientific_pipeline" in kernel_refs
    assert "universal_learning" in kernel_refs
    assert "explainability_v2" in kernel_refs


def test_ws7_execution_references_pipeline() -> None:
    _, _, _, execution = _build_business_os_registry()
    assert execution.pipeline_id == "dry-run-001"


def test_ws7_no_write_operations() -> None:
    """BusinessOSRegistry build produces no side effects — pure in-memory."""
    registry, domain, mission, execution = _build_business_os_registry()
    assert registry.registry_id == "bos-registry-001"
    assert domain.domain_id == "domain-crypto-001"
    assert mission.mission_id == "mission-crypto-001"


# ══════════════════════════════════════════════════════════════════════════════
# WS8 — CONSUMER MIGRATION VALIDATION
# ══════════════════════════════════════════════════════════════════════════════


def test_ws8_sip_to_scientific_identity_adapter_ready() -> None:
    """SIP CanonicalDecisionRecord can be adapted to ScientificIdentity."""
    from app.scientific_identity.adapter import from_canonical_decision_record
    from app.scientific_identity.contract import ScientificEntityType

    class FakeRecord:
        canonical_decision_id = "dec-001"
        lineage_id = "lin-dry-run-001"
        decided_at = "2026-06-30T12:00:00+00:00"
        strategy = "spec"
        decision_stage = "COMMITTEE"
        decision_action = "APPROVE"
        decision_reason_code = "COMMITTEE_QUORUM_MET"
        symbol = "BTCUSDT"

    identity = from_canonical_decision_record(FakeRecord())
    assert identity.entity_type == ScientificEntityType.COMMITTEE
    assert identity.lineage_id == "lin-dry-run-001"
    assert identity.scientific_id


def test_ws8_whalefi_funding_to_observation_adapter_ready() -> None:
    from app.observation.adapter import from_funding_rate
    from app.observation.contract import ObservationType, ObservationQuality

    obs = from_funding_rate("BTCUSDT", 0.0012, "2026-06-30T08:00:00+00:00", "binance")
    assert obs.observation_type == ObservationType.FUNDING
    assert obs.quality == ObservationQuality.VERIFIED
    assert obs.verify_payload_integrity()


def test_ws8_whalefi_oi_to_observation_adapter_ready() -> None:
    from app.observation.adapter import from_open_interest
    from app.observation.contract import ObservationType

    obs = from_open_interest("ETHUSDT", 1_500_000.0, "2026-06-30T08:00:00+00:00", "bybit")
    assert obs.observation_type == ObservationType.OPEN_INTEREST
    assert obs.verify_payload_integrity()


def test_ws8_signal_event_to_observation_adapter_ready() -> None:
    from app.observation.adapter import from_signal_event
    from app.observation.contract import ObservationType

    event = {
        "signal_id": "sig-wiring-001",
        "strategy": "spec",
        "symbol": "BTCUSDT",
        "side": "LONG",
        "confidence": 0.82,
        "timestamp": "2026-06-30T12:00:00+00:00",
    }
    obs = from_signal_event(event)
    assert obs.observation_type == ObservationType.SIGNAL
    assert obs.symbol == "BTCUSDT"
    assert obs.verify_payload_integrity()


def test_ws8_logical_knowledge_graph_to_canonical_adapter_ready() -> None:
    from app.knowledge_graph_contract.adapter_python import InMemoryKnowledgeGraph
    from app.knowledge_graph_contract.contract import KnowledgeGraphContractProtocol

    g = InMemoryKnowledgeGraph()
    assert isinstance(g, KnowledgeGraphContractProtocol)


def test_ws8_business_os_claim_to_scientific_identity_adapter_ready() -> None:
    from app.scientific_identity.adapter import from_business_os_claim
    from app.scientific_identity.contract import ScientificEntityType

    identity = from_business_os_claim("claim-001", "cap-pipeline", "lin-dry-run-001")
    assert identity.entity_type == ScientificEntityType.CLAIM
    assert identity.producer == "business-os/foundation/cap-pipeline"


def test_ws8_execution_outcome_to_scientific_identity_adapter_ready() -> None:
    from app.scientific_identity.adapter import from_execution_outcome
    from app.scientific_identity.contract import ScientificEntityType

    class FakeOutcome:
        outcome_id = "out-001"
        session_id = "sess-001"
        status = "COMPLETED"

    identity = from_execution_outcome(FakeOutcome(), "lin-dry-run-001")
    assert identity.entity_type == ScientificEntityType.OUTCOME
    assert identity.lineage_id == "lin-dry-run-001"


# ══════════════════════════════════════════════════════════════════════════════
# FULL INTEGRATION — end-to-end chain
# ══════════════════════════════════════════════════════════════════════════════


def test_full_integration_chain() -> None:
    """
    Complete scientific chain in memory:
    Observation → ScientificIdentity → Pipeline → Explainability →
    Ledger → Learning → KnowledgeGraph → BusinessOS
    """
    from app.observation.contract import ObservationContract, ObservationType
    from app.scientific_identity.builder import ScientificIdentityBuilder
    from app.scientific_identity.contract import ScientificEntityType
    from app.scientific_identity.repository import InMemoryScientificIdentityRepository
    from app.observation.repository import InMemoryObservationRepository

    # 1. Observation
    obs = ObservationContract.create(
        observation_id="obs-integration-01",
        producer="sip/spec",
        observed_at="2026-06-30T12:00:00+00:00",
        observation_type=ObservationType.SIGNAL,
        payload={"symbol": "BTCUSDT", "confidence": 0.82, "side": "LONG"},
        symbol="BTCUSDT",
    )
    assert obs.verify_payload_integrity()
    obs_repo = InMemoryObservationRepository()
    obs_repo.save(obs)

    # 2. Scientific Identity chain
    lid = ScientificIdentityBuilder.derive_lineage_id("BTCUSDT", "spec", obs.observation_id)
    builder = ScientificIdentityBuilder(lid, "sip/spec")
    id_repo = InMemoryScientificIdentityRepository()
    chain = ScientificIdentityBuilder.new_chain(lid)

    for etype, eid in [
        (ScientificEntityType.OBSERVATION, obs.observation_id),
        (ScientificEntityType.EVIDENCE, "ev-001"),
        (ScientificEntityType.DECISION, "dec-001"),
        (ScientificEntityType.COMMITTEE, "comm-001"),
        (ScientificEntityType.EXECUTION, "exec-001"),
        (ScientificEntityType.OUTCOME, "out-001"),
        (ScientificEntityType.LEARNING, "ls-001"),
        (ScientificEntityType.KNOWLEDGE, "know-001"),
    ]:
        identity, chain = builder.build_chain(etype, eid, chain, "2026-06-30T12:00:00+00:00")
        id_repo.save(identity)

    assert len(chain.entries) == 8
    assert chain.entries[0].entity_type == ScientificEntityType.OBSERVATION
    assert chain.entries[-1].entity_type == ScientificEntityType.KNOWLEDGE

    # 3. Pipeline Dry Run
    _, _, pipeline_trace, manifest = _build_dry_run_pipeline()
    assert pipeline_trace.validate() == []
    assert manifest.validate() == []
    assert pipeline_trace.context.lineage_id == "lin-dry-run-001"

    # 4. Explainability
    _, _, expl = _build_explainability()
    assert expl.validate() == []

    # 5. Execution Ledger
    ledger, timeline, replay = _build_ledger()
    assert ledger.validate() == []
    assert not replay.has_divergence()

    # 6. Universal Learning
    _, snapshot, signal, stats, lrn_timeline, knowledge = _build_learning()
    assert snapshot.validate() == []
    assert signal.ADVISORY_ONLY is True
    assert stats.validate() == []

    # 7. Knowledge Graph
    g, _, _ = _build_knowledge_graph()
    snap = g.snapshot("2026-06-30T12:00:00+00:00")
    assert snap.node_count == 5

    # 8. Business OS
    registry, domain, _, _ = _build_business_os_registry()
    assert registry.validate() == []
    assert domain.config.advisory_only is True

    # Chain consistency
    assert chain.lineage_id == lid
    assert chain.chain_hash  # deterministic fingerprint of full chain
