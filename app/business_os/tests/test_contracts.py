from app.business_os.contracts import (
    BusinessOSExecution,
    BusinessOSProject,
    BusinessOSRegistry,
    BusinessSnapshot,
    CapabilityRef,
    CapabilityStatus,
    DomainCapability,
    DomainKind,
    DomainKnowledge,
    EvaluationBundle,
    ExecutionDomain,
    ExecutionDomainConfig,
    ExecutionStatus,
    Mission,
    MissionObjective,
    MissionStatus,
    Opportunity,
    OpportunitySignal,
    OpportunityStatus,
    Outcome,
    OutcomeKind,
    ProjectExecution,
    ProjectStatus,
    RankingScore,
)


def _cap_ref() -> CapabilityRef:
    return CapabilityRef(capability_id="cap-001", kernel_ref="scientific_kernel.evidence", description="Evidence kernel")


def _domain_cap() -> DomainCapability:
    return DomainCapability(
        capability_id="cap-001",
        domain=DomainKind.CRYPTO,
        capability_ref=_cap_ref(),
        status=CapabilityStatus.AVAILABLE,
        version="v1",
        last_checked_at="2026-06-30T00:00:00Z",
    )


def _exec_domain() -> ExecutionDomain:
    return ExecutionDomain(
        domain_id="dom-001",
        kind=DomainKind.CRYPTO,
        pipeline_ref="app.scientific_pipeline",
        capabilities=(_domain_cap(),),
        config=ExecutionDomainConfig(),
    )


def _mission() -> Mission:
    return Mission(
        mission_id="m-001",
        domain=DomainKind.CRYPTO,
        title="Mirror Execution",
        status=MissionStatus.ACTIVE,
        objectives=(
            MissionObjective(objective_id="o1", description="Positive ROI", metric="roi", target=0.05, unit="%"),
        ),
        created_at="2026-06-30T00:00:00Z",
    )


def test_mission_validates() -> None:
    assert _mission().validate() == []


def test_mission_missing_title() -> None:
    m = Mission(
        mission_id="m-001",
        domain=DomainKind.CRYPTO,
        title="",
        status=MissionStatus.ACTIVE,
        objectives=(MissionObjective(objective_id="o1", description="x", metric="roi"),),
        created_at="t",
    )
    errors = m.validate()
    assert any("title" in e for e in errors)


def test_mission_requires_objectives() -> None:
    m = Mission(mission_id="m-001", domain=DomainKind.CRYPTO, title="T", status=MissionStatus.ACTIVE, objectives=(), created_at="t")
    errors = m.validate()
    assert any("objective" in e for e in errors)


def test_domain_capability_validates() -> None:
    assert _domain_cap().validate() == []


def test_execution_domain_validates() -> None:
    assert _exec_domain().validate() == []


def test_execution_domain_has_capability() -> None:
    dom = _exec_domain()
    assert dom.has_capability("cap-001")
    assert not dom.has_capability("cap-999")


def test_opportunity_validates() -> None:
    signal = OpportunitySignal(signal_id="s1", source="mirror", strength=0.8, captured_at="t")
    opp = Opportunity(
        opportunity_id="opp-001",
        domain=DomainKind.CRYPTO,
        status=OpportunityStatus.DISCOVERED,
        signals=(signal,),
        confidence=0.75,
        expected_value=0.04,
        discovered_at="2026-06-30T00:00:00Z",
    )
    assert opp.validate() == []


def test_opportunity_invalid_confidence() -> None:
    opp = Opportunity(
        opportunity_id="opp-001",
        domain=DomainKind.CRYPTO,
        status=OpportunityStatus.DISCOVERED,
        signals=(),
        confidence=2.0,
        expected_value=None,
        discovered_at="t",
    )
    errors = opp.validate()
    assert any("confidence" in e for e in errors)


def test_signal_invalid_strength() -> None:
    signal = OpportunitySignal(signal_id="s1", source="x", strength=1.5, captured_at="t")
    assert signal.validate() != []


def test_outcome_edge_delta() -> None:
    outcome = Outcome(
        outcome_id="out-001",
        domain=DomainKind.CRYPTO,
        opportunity_id="opp-001",
        kind=OutcomeKind.SUCCESS,
        realized_value=0.05,
        expected_value=0.03,
        recorded_at="t",
    )
    assert outcome.validate() == []
    assert abs(outcome.edge_delta() - 0.02) < 1e-9


def test_outcome_edge_delta_none_when_missing_values() -> None:
    outcome = Outcome(
        outcome_id="out-001",
        domain=DomainKind.CRYPTO,
        opportunity_id="opp-001",
        kind=OutcomeKind.INCONCLUSIVE,
        realized_value=None,
        expected_value=None,
        recorded_at="t",
    )
    assert outcome.edge_delta() is None


def test_domain_knowledge_validates() -> None:
    k = DomainKnowledge(
        knowledge_id="k-001",
        domain=DomainKind.CRYPTO,
        claim="B2B_FADE positive edge confirmed",
        confidence=0.8,
        evidence_refs=("ev-001",),
        created_at="t",
    )
    assert k.validate() == []


def test_domain_knowledge_no_evidence_invalid() -> None:
    k = DomainKnowledge(
        knowledge_id="k-001",
        domain=DomainKind.SEO,
        claim="claim without evidence",
        confidence=0.5,
        evidence_refs=(),
        created_at="t",
    )
    errors = k.validate()
    assert any("evidence" in e for e in errors)


def test_project_validates() -> None:
    project = BusinessOSProject(
        project_id="proj-001",
        domain=DomainKind.CRYPTO,
        mission_ref="m-001",
        status=ProjectStatus.ACTIVE,
        execution_domain=_exec_domain(),
        capabilities=(_domain_cap(),),
        created_at="2026-06-30T00:00:00Z",
    )
    assert project.validate() == []


def test_execution_validates() -> None:
    ex = BusinessOSExecution(
        execution_id="ex-001",
        domain=DomainKind.CRYPTO,
        project_id="proj-001",
        pipeline_id="pipe-001",
        opportunity_id="opp-001",
        status=ExecutionStatus.COMPLETED,
        initiated_at="2026-06-30T00:00:00Z",
    )
    assert ex.validate() == []


def test_registry_active_domains() -> None:
    dom = _exec_domain()
    inactive = ExecutionDomain(
        domain_id="dom-002",
        kind=DomainKind.SEO,
        pipeline_ref="app.scientific_pipeline",
        capabilities=(),
        config=ExecutionDomainConfig(),
        active=False,
    )
    project = BusinessOSProject(
        project_id="proj-001",
        domain=DomainKind.CRYPTO,
        mission_ref="m-001",
        status=ProjectStatus.ACTIVE,
        execution_domain=dom,
        capabilities=(),
        created_at="t",
    )
    registry = BusinessOSRegistry(registry_id="reg-001", projects=(project,), domains=(dom, inactive))
    active = registry.active_domains()
    assert len(active) == 1
    assert active[0].domain_id == "dom-001"


def test_registry_project_for_domain() -> None:
    dom = _exec_domain()
    project = BusinessOSProject(
        project_id="proj-001",
        domain=DomainKind.CRYPTO,
        mission_ref="m-001",
        status=ProjectStatus.ACTIVE,
        execution_domain=dom,
        capabilities=(),
        created_at="t",
    )
    registry = BusinessOSRegistry(registry_id="reg-001", projects=(project,), domains=(dom,))
    assert registry.project_for_domain(DomainKind.CRYPTO) == (project,)
    assert registry.project_for_domain(DomainKind.SEO) == ()


def test_evaluation_bundle_validates() -> None:
    bundle = EvaluationBundle(
        bundle_id="eval-001",
        domain=DomainKind.CRYPTO,
        evidence_refs=("ev-001", "ev-002"),
        context_ref="ctx-001",
        statistics_ref="stats-001",
        confidence_ref="conf-001",
        explainability_ref="expl-001",
        replay_ref=None,
        evaluated_at="2026-06-30T00:00:00Z",
    )
    assert bundle.validate() == []


def test_evaluation_bundle_requires_at_least_one_reference() -> None:
    bundle = EvaluationBundle(
        bundle_id="eval-001",
        domain=DomainKind.CRYPTO,
        evidence_refs=(),
        context_ref=None,
        statistics_ref=None,
        confidence_ref=None,
        explainability_ref=None,
        replay_ref=None,
        evaluated_at="t",
    )
    errors = bundle.validate()
    assert any("reference" in e for e in errors)


def test_ranking_score_validates() -> None:
    ranking = RankingScore(
        ranking_id="rank-001",
        opportunity_ref="opp-001",
        confidence_ref="conf-001",
        priority=0.7,
        impact=0.9,
        roi=0.12,
        urgency=0.5,
        computed_at="2026-06-30T00:00:00Z",
    )
    assert ranking.validate() == []


def test_ranking_score_invalid_priority() -> None:
    ranking = RankingScore(
        ranking_id="rank-001",
        opportunity_ref="opp-001",
        confidence_ref=None,
        priority=1.5,
        impact=0.5,
        roi=None,
        urgency=None,
        computed_at="t",
    )
    errors = ranking.validate()
    assert any("priority" in e for e in errors)


def test_ranking_score_missing_opportunity_ref() -> None:
    ranking = RankingScore(
        ranking_id="rank-001",
        opportunity_ref="",
        confidence_ref=None,
        priority=0.5,
        impact=0.5,
        roi=None,
        urgency=None,
        computed_at="t",
    )
    errors = ranking.validate()
    assert any("opportunity_ref" in e for e in errors)


def test_business_snapshot_validates() -> None:
    snapshot = BusinessSnapshot(
        snapshot_id="snap-001",
        domain=DomainKind.CRYPTO,
        captured_at="2026-06-30T00:00:00Z",
        opportunity_ref="opp-001",
        evaluation_ref="eval-001",
        ranking_ref="rank-001",
        execution_plan_ref=None,
        execution_ref=None,
        outcome_ref=None,
        learning_ref=None,
    )
    assert snapshot.validate() == []


def test_business_snapshot_requires_snapshot_id() -> None:
    snapshot = BusinessSnapshot(
        snapshot_id="",
        domain=DomainKind.CRYPTO,
        captured_at="t",
        opportunity_ref=None,
        evaluation_ref=None,
        ranking_ref=None,
        execution_plan_ref=None,
        execution_ref=None,
        outcome_ref=None,
        learning_ref=None,
    )
    errors = snapshot.validate()
    assert any("snapshot_id" in e for e in errors)
