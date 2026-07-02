"""Business OS 6.0 Phase 1 — Opportunity Emitters.

Validates that Research Lab and Poupi Baby raw records, already produced by
their own domain logic, become canonical ``Opportunity`` instances with full
Observer Framework coverage (Replay, Explainability, Learning Feed, Runtime
Snapshot) and correct composition into EvaluationBundle/RankingScore/
BusinessSnapshot — without recomputing any statistic and without duplicating
any contract.
"""
from __future__ import annotations

from app.business_os.contracts import DomainKind, OpportunityStatus
from app.business_os.opportunity_emitters import (
    OpportunityRegistry,
    build_opportunity_from_poupi_baby,
    build_opportunity_from_research,
    emit_opportunity,
)
from app.universal_platform.adapters.poupi_baby_opportunity_adapter import (
    PoupiBabyOpportunityAdapter,
)
from app.universal_platform.adapters.research_opportunity_adapter import (
    ResearchOpportunityAdapter,
)


def _research_raw() -> dict:
    return {
        "opportunity_id": "opp-research-001",
        "scientific_id": "sci-abc",
        "experiment_id": "exp-42",
        "hypothesis_id": "hyp-7",
        "title": "Mean-reversion edge on BTC funding regime",
        "description": "Detected via Research Lab statistical validation",
        "feature_set": ("funding_rate_z", "oi_delta"),
        "regimes_valid": ["RANGE", "LOW_VOL"],
        "assets_valid": ["BTCUSDT"],
        "scientific_score": 71.5,
        "confidence": 0.82,
        "promotion_status": "SCIENTIFIC_APPROVED",
        "committee_preview": None,
        "created_at": "2026-07-01T12:00:00Z",
    }


def _poupi_baby_raw() -> dict:
    return {
        "id": "opp-baby-001",
        "verticalId": "vert-babygear",
        "assetId": "asset-blog-1",
        "sourceIds": ["src-amazon"],
        "title": "Stroller comparison content gap",
        "summary": "High search volume, low competing content",
        "confidence": 0.68,
        "estimatedRoi": 2.4,
        "estimatedMarketSize": 50000,
        "competitionScore": 0.3,
        "complexityScore": 0.2,
        "priority": 0.9,
        "discovered_at": "2026-07-01T09:00:00Z",
        "evidence": [
            {"kind": "metric", "value": "search_volume:12000", "weight": 0.7},
            {"kind": "url", "value": "https://example.com/serp", "weight": 0.5},
        ],
        "status": "active",
    }


def test_research_opportunity_emission_full_coverage() -> None:
    registry = OpportunityRegistry()
    adapter = ResearchOpportunityAdapter()
    raw = _research_raw()

    emission = emit_opportunity(
        adapter=adapter,
        registry=registry,
        raw=raw,
        build_opportunity=build_opportunity_from_research,
    )

    opp = emission.opportunity
    assert opp.opportunity_id == raw["opportunity_id"]
    assert opp.domain == DomainKind.CRYPTO
    assert opp.status == OpportunityStatus.EVALUATED
    assert opp.confidence == raw["confidence"]  # passthrough, no recomputation
    assert opp.expected_value == raw["scientific_score"]  # passthrough
    assert opp.validate() == []

    # Observer Framework: full chain materialised for this Opportunity.
    coverage = emission.observation.coverage
    assert coverage.is_complete, coverage.as_dict()
    assert "explainability" in coverage.present
    assert "replay_manifest" in coverage.present
    assert "learning_feed" in coverage.present
    assert emission.observation.audit.snapshot_id  # Runtime Snapshot published

    # Business OS registration reuses RankingScore/BusinessSnapshot/EvaluationBundle.
    reg = emission.registration
    assert reg.ranking.opportunity_ref == opp.opportunity_id
    assert reg.ranking.priority == opp.confidence  # no new ranking engine
    assert reg.ranking.roi == opp.expected_value
    assert reg.snapshot.opportunity_ref == opp.opportunity_id
    assert reg.snapshot.ranking_ref == reg.ranking.ranking_id
    assert reg.snapshot.evaluation_ref == reg.evaluation.bundle_id
    assert reg.snapshot.learning_ref == emission.lineage_id


def test_poupi_baby_opportunity_emission_full_coverage() -> None:
    registry = OpportunityRegistry()
    adapter = PoupiBabyOpportunityAdapter()
    raw = _poupi_baby_raw()

    emission = emit_opportunity(
        adapter=adapter,
        registry=registry,
        raw=raw,
        build_opportunity=build_opportunity_from_poupi_baby,
        build_opportunity_kwargs={"discovered_at": "2026-07-01T09:00:00Z"},
    )

    opp = emission.opportunity
    assert opp.opportunity_id == raw["id"]
    assert opp.domain == DomainKind.AFFILIATE
    assert opp.status == OpportunityStatus.EVALUATED
    assert opp.confidence == raw["confidence"]
    assert opp.expected_value == raw["estimatedRoi"]
    assert len(opp.evidence_refs) == 2
    assert opp.validate() == []

    coverage = emission.observation.coverage
    assert coverage.is_complete, coverage.as_dict()

    reg = emission.registration
    assert reg.evaluation.evidence_refs == opp.evidence_refs
    assert reg.snapshot.domain == DomainKind.AFFILIATE


def test_two_domains_register_distinct_opportunities_no_duplication() -> None:
    registry = OpportunityRegistry()

    research_emission = emit_opportunity(
        adapter=ResearchOpportunityAdapter(),
        registry=registry,
        raw=_research_raw(),
        build_opportunity=build_opportunity_from_research,
    )
    baby_emission = emit_opportunity(
        adapter=PoupiBabyOpportunityAdapter(),
        registry=registry,
        raw=_poupi_baby_raw(),
        build_opportunity=build_opportunity_from_poupi_baby,
        build_opportunity_kwargs={"discovered_at": "2026-07-01T09:00:00Z"},
    )

    assert registry.count() == 2
    ids = {r.opportunity.opportunity_id for r in registry.all()}
    assert ids == {research_emission.opportunity.opportunity_id, baby_emission.opportunity.opportunity_id}

    # Each registration carries its own EvaluationBundle/RankingScore/BusinessSnapshot —
    # no shared/duplicated contract instance between domains.
    reg_a = registry.get(research_emission.opportunity.opportunity_id)
    reg_b = registry.get(baby_emission.opportunity.opportunity_id)
    assert reg_a is not None and reg_b is not None
    assert reg_a.evaluation.bundle_id != reg_b.evaluation.bundle_id
    assert reg_a.ranking.ranking_id != reg_b.ranking.ranking_id
    assert reg_a.snapshot.snapshot_id != reg_b.snapshot.snapshot_id
    assert reg_a.opportunity.domain != reg_b.opportunity.domain


def test_adapters_remain_read_only_advisory_shadow() -> None:
    for adapter in (ResearchOpportunityAdapter(), PoupiBabyOpportunityAdapter()):
        descriptor = adapter.descriptor()
        assert descriptor["shadow_mode"] is True
        assert descriptor["read_only"] is True
        assert descriptor["advisory_only"] is True
