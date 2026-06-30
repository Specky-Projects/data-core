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
    dependency_graph,
    execution_order,
)


def _ctx() -> PipelineContext:
    return PipelineContext(
        pipeline_id="pipe-001",
        domain="crypto",
        candidate_id="cand-001",
        lineage_id="lin-001",
        initiated_at="2026-06-30T00:00:00Z",
        initiator="test",
    )


def test_pipeline_context_validates_required_fields() -> None:
    assert _ctx().validate() == []


def test_pipeline_context_missing_fields() -> None:
    ctx = PipelineContext(
        pipeline_id="",
        domain="",
        candidate_id="x",
        lineage_id="y",
        initiated_at="t",
        initiator="z",
    )
    errors = ctx.validate()
    assert "pipeline_id is required" in errors
    assert "domain is required" in errors


def test_stage_order_matches_pipeline_definition() -> None:
    order = execution_order()
    assert order == STAGE_ORDER
    assert StageKind.CONTEXT == order[0]
    assert StageKind.LEARNING == order[-1]


def test_all_stages_have_contracts() -> None:
    for kind in StageKind:
        assert kind in STAGE_CONTRACTS, f"missing contract for {kind}"


def test_stage_contract_dependency_graph_is_acyclic() -> None:
    graph = dependency_graph()
    for stage, deps in graph.items():
        assert stage not in deps, f"{stage} depends on itself"


def test_stage_contract_validates_missing_input() -> None:
    contract = STAGE_CONTRACTS[StageKind.EVIDENCE]
    errors = contract.validate_input({})
    assert any("context_snapshot" in e for e in errors)


def test_stage_contract_validates_missing_output() -> None:
    contract = STAGE_CONTRACTS[StageKind.BAYESIAN]
    errors = contract.validate_output({})
    assert any("posterior" in e for e in errors)


def test_stage_output_passed() -> None:
    out = StageOutput(stage=StageKind.CONTEXT, status=StageStatus.PASSED)
    assert out.passed()


def test_stage_output_failed() -> None:
    out = StageOutput(stage=StageKind.CONTEXT, status=StageStatus.FAILED)
    assert not out.passed()


def test_pipeline_state_terminal_statuses() -> None:
    ctx = _ctx()
    for terminal in (PipelineStatus.COMPLETED, PipelineStatus.FAILED, PipelineStatus.BLOCKED):
        state = PipelineState(context=ctx, status=terminal, current_stage=None)
        assert state.is_terminal()


def test_pipeline_state_non_terminal() -> None:
    state = PipelineState(context=_ctx(), status=PipelineStatus.RUNNING, current_stage=StageKind.EVIDENCE)
    assert not state.is_terminal()


def test_pipeline_trace_validates_required_fields() -> None:
    trace = PipelineTrace(
        pipeline_id="p1",
        context=_ctx(),
        final_status=PipelineStatus.COMPLETED,
        stages=(),
        total_duration_ms=10.0,
        initiated_at="2026-06-30T00:00:00Z",
        finished_at="2026-06-30T00:00:01Z",
    )
    assert trace.validate() == []


def test_pipeline_trace_failed_stages() -> None:
    st = StageTrace(
        stage=StageKind.BAYESIAN,
        status=StageStatus.FAILED,
        input_hash=None,
        output_hash=None,
        duration_ms=None,
    )
    trace = PipelineTrace(
        pipeline_id="p1",
        context=_ctx(),
        final_status=PipelineStatus.FAILED,
        stages=(st,),
        total_duration_ms=5.0,
        initiated_at="2026-06-30T00:00:00Z",
        finished_at=None,
    )
    assert trace.failed_stages() == (st,)


def test_replay_manifest_requires_inputs() -> None:
    trace = PipelineTrace(
        pipeline_id="p1",
        context=_ctx(),
        final_status=PipelineStatus.COMPLETED,
        stages=(),
        total_duration_ms=1.0,
        initiated_at="2026-06-30T00:00:00Z",
        finished_at="2026-06-30T00:00:01Z",
    )
    manifest = PipelineReplayManifest(
        pipeline_id="p1",
        original_trace=trace,
        replay_inputs=(),
    )
    errors = manifest.validate()
    assert "replay_inputs must not be empty" in errors


def test_replay_manifest_valid() -> None:
    trace = PipelineTrace(
        pipeline_id="p1",
        context=_ctx(),
        final_status=PipelineStatus.COMPLETED,
        stages=(),
        total_duration_ms=1.0,
        initiated_at="2026-06-30T00:00:00Z",
        finished_at="2026-06-30T00:00:01Z",
    )
    ri = ReplayInput(stage=StageKind.CONTEXT, payload_hash="abc", evidence_refs=())
    manifest = PipelineReplayManifest(pipeline_id="p1", original_trace=trace, replay_inputs=(ri,))
    assert manifest.validate() == []


def test_scientific_decision_pipeline_is_abstract() -> None:
    pipeline = ScientificDecisionPipeline()
    try:
        pipeline.run(_ctx())
        assert False, "should raise"
    except NotImplementedError:
        pass
