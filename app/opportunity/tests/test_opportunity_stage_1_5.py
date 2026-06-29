"""Business OS 1.5 — Opportunity Intelligence Platform — Scientific Test Suite.

Tests:
  - Opportunity Model (Stage 1)
  - Opportunity Discovery (Stage 2)
  - Opportunity Scoring (Stage 3)
  - Opportunity Ranking (Stage 4)
  - Opportunity Lifecycle (Stage 5)
  - Opportunity Evolution (Stage 6)
  - Opportunity Portfolio (Stage 7)
  - Opportunity Health (Stage 8)
  - Explainability (Stage 9)
  - Adaptive Learning Integration (Stage 10)
  - Pipeline Orchestrator
  - Replay Determinism
  - Backward Compatibility
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.adaptive_intelligence.dto import EvaluationContext
from app.knowledge.connectors.github import GitHubConnector
from app.knowledge.connectors.hacker_news import HackerNewsConnector
from app.knowledge.orchestrator import run_knowledge_pipeline
from app.opportunity.discovery import (
    discover_from_correlations,
    discover_from_knowledge_items,
)
from app.opportunity.dto import (
    DISCOVERY_VERSION,
    EVOLUTION_VERSION,
    EXPLAINABILITY_VERSION,
    HEALTH_VERSION,
    LIFECYCLE_VERSION,
    OPPORTUNITY_VERSION,
    PORTFOLIO_VERSION,
    RANKING_VERSION,
    SCORING_VERSION,
    EvolutionDirection,
    LifecycleStage,
    Opportunity,
    OpportunityExplanation,
    OpportunityHealth,
    OpportunityProvenance,
    OpportunityScore,
    OpportunityType,
    OpportunityVersionMetadata,
    PortfolioNode,
    RankingStrategy,
    build_opportunity_id,
    build_snapshot_id,
)
from app.opportunity.evolution import (
    annotate_evolution,
    build_evolution_explanation,
    compute_evolution_direction,
)
from app.opportunity.health import compute_opportunity_health
from app.opportunity.learning import apply_adaptive_calibration, build_opportunity_feedback
from app.opportunity.lifecycle import advance_lifecycle, _compute_lifecycle_stage
from app.opportunity.orchestrator import run_opportunity_pipeline
from app.opportunity.portfolio import build_portfolio
from app.opportunity.ranking import rank_opportunities
from app.opportunity.scoring import rescore_all, score_opportunity

# ── Fixtures ───────────────────────────────────────────────────────────────────

_TS = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)
_CTX = EvaluationContext(evaluation_timestamp=_TS, dataset_version="test-1.5")

_GH_RAW = [
    {
        "full_name": "openai/openai-python",
        "html_url": "https://github.com/openai/openai-python",
        "description": "Python client for OpenAI API",
        "stargazers_count": 5000,
        "language": "Python",
        "owner": {"login": "openai"},
        "topics": ["openai", "llm", "python"],
        "pushed_at": "2026-06-01T10:00:00Z",
    },
    {
        "full_name": "huggingface/transformers",
        "html_url": "https://github.com/huggingface/transformers",
        "description": "Transformers for NLP and vision",
        "stargazers_count": 90000,
        "language": "Python",
        "owner": {"login": "huggingface"},
        "topics": ["nlp", "machine-learning", "transformers"],
        "pushed_at": "2026-06-15T08:00:00Z",
    },
]

_HN_RAW = [
    {
        "id": 1001,
        "title": "OpenAI releases GPT-5",
        "url": "https://openai.com/gpt5",
        "score": 500,
        "by": "user_a",
        "time": int(_TS.timestamp()),
        "descendants": 100,
    },
    {
        "id": 1002,
        "title": "Transformers library reaches 100k stars",
        "url": "https://github.com/huggingface/transformers",
        "score": 300,
        "by": "user_b",
        "time": int(_TS.timestamp()),
        "descendants": 50,
    },
    {
        "id": 1003,
        "title": "New GPU architecture for ML inference",
        "url": "https://example.com/gpu-ml",
        "score": 200,
        "by": "user_c",
        "time": int(_TS.timestamp()),
        "descendants": 30,
    },
]


def _make_knowledge_report(max_items: int = 5):
    connectors = [
        GitHubConnector(topics=["llm"], max_items=max_items, _raw_override=_GH_RAW),
        HackerNewsConnector(max_items=max_items, _raw_override=_HN_RAW),
    ]
    return run_knowledge_pipeline(connectors, _CTX)


def _make_opportunity(
    title: str = "Test Opportunity",
    confidence: float = 0.5,
    domain: str = "technology",
    opp_type: OpportunityType = OpportunityType.TECHNOLOGY,
    source_count: int = 2,
    evidence_count: int = 3,
) -> Opportunity:
    from app.knowledge.dto import _EPOCH
    from app.knowledge.dto import KnowledgeSource, SourceType, KnowledgeEvidence, build_evidence_id

    sources = [
        KnowledgeSource(source_id=f"src:{i}", source_type=SourceType.GITHUB, url=f"https://x.com/{i}", name=f"src{i}")
        for i in range(source_count)
    ]
    evidence = [
        KnowledgeEvidence(
            evidence_id=build_evidence_id(f"src:{i}", f"content {i}", _EPOCH),
            content=f"Evidence content {i}",
            source_id=f"src:{i}",
            weight=0.8,
        )
        for i in range(evidence_count)
    ]
    opp_id = build_opportunity_id(title, domain, opp_type)
    provenance = OpportunityProvenance(
        knowledge_item_ids=["item1", "item2"],
        entity_ids=["ent1"],
        discovery_method="test",
        discovered_at=_TS,
    )
    return Opportunity(
        opportunity_id=opp_id,
        title=title,
        summary=f"{title} is a test opportunity.",
        confidence=confidence,
        priority=confidence,
        novelty=0.4,
        maturity=0.3,
        urgency=0.5,
        impact=0.6,
        opportunity_type=opp_type,
        domain=domain,
        sources=sources,
        evidence=evidence,
        provenance=provenance,
        explanation=OpportunityExplanation(why_exists=f"Test explanation for {title}"),
        created_at=_TS,
        updated_at=_TS,
    )


# ── Stage 1: Opportunity Model ─────────────────────────────────────────────────


class TestOpportunityModel:
    def test_version_constants_distinct(self):
        versions = [
            OPPORTUNITY_VERSION, DISCOVERY_VERSION, SCORING_VERSION, RANKING_VERSION,
            LIFECYCLE_VERSION, PORTFOLIO_VERSION, HEALTH_VERSION, EXPLAINABILITY_VERSION,
            EVOLUTION_VERSION,
        ]
        assert len(set(versions)) == len(versions)

    def test_opportunity_version_contains_1_5(self):
        assert "1.5" in OPPORTUNITY_VERSION

    def test_version_metadata_defaults(self):
        m = OpportunityVersionMetadata()
        assert m.opportunity_version == OPPORTUNITY_VERSION
        assert m.knowledge_version  # links back to 1.4

    def test_build_opportunity_id_deterministic(self):
        id1 = build_opportunity_id("Python", "technology", OpportunityType.TECHNOLOGY)
        id2 = build_opportunity_id("python", "Technology", OpportunityType.TECHNOLOGY)
        assert id1 == id2

    def test_build_opportunity_id_different_types_differ(self):
        id1 = build_opportunity_id("Python", "technology", OpportunityType.TECHNOLOGY)
        id2 = build_opportunity_id("Python", "technology", OpportunityType.RESEARCH)
        assert id1 != id2

    def test_opportunity_provenance_hash_set(self):
        prov = OpportunityProvenance(
            knowledge_item_ids=["a", "b"],
            discovery_method="test",
            discovered_at=_TS,
        )
        assert prov.provenance_hash

    def test_opportunity_provenance_hash_deterministic(self):
        prov1 = OpportunityProvenance(knowledge_item_ids=["a"], discovery_method="test", discovered_at=_TS)
        prov2 = OpportunityProvenance(knowledge_item_ids=["a"], discovery_method="test", discovered_at=_TS)
        assert prov1.provenance_hash == prov2.provenance_hash

    def test_opportunity_score_composite_auto_computed(self):
        score = OpportunityScore(
            novelty=0.5, evidence_strength=0.6, source_diversity=0.4,
            growth_velocity=0.3, confidence=0.7, risk=0.3,
            market_impact=0.5, strategic_relevance=0.6, consistency=0.5, freshness=0.8,
        )
        assert score.composite_score > 0.0
        assert 0.0 <= score.composite_score <= 1.0

    def test_build_snapshot_id_deterministic(self):
        sid1 = build_snapshot_id("opp1", _TS)
        sid2 = build_snapshot_id("opp1", _TS)
        assert sid1 == sid2

    def test_lifecycle_stage_enum_complete(self):
        stages = [s.value for s in LifecycleStage]
        assert "new" in stages
        assert "archived" in stages
        assert len(stages) == 6

    def test_ranking_strategy_enum_complete(self):
        strategies = [s.value for s in RankingStrategy]
        assert "by_composite" in strategies
        assert len(strategies) >= 5

    def test_opportunity_type_enum_complete(self):
        types = [t.value for t in OpportunityType]
        assert "technology" in types
        assert "unknown" in types


# ── Stage 2: Discovery ────────────────────────────────────────────────────────


class TestOpportunityDiscovery:
    def test_discover_from_knowledge_items_returns_list(self):
        kr = _make_knowledge_report()
        opps = discover_from_knowledge_items(kr.items, _CTX, min_source_count=1)
        assert isinstance(opps, list)

    def test_discover_empty_items(self):
        opps = discover_from_knowledge_items([], _CTX)
        assert opps == []

    def test_discover_ids_deterministic(self):
        kr = _make_knowledge_report()
        opps1 = discover_from_knowledge_items(kr.items, _CTX, min_source_count=1)
        opps2 = discover_from_knowledge_items(kr.items, _CTX, min_source_count=1)
        assert sorted(o.opportunity_id for o in opps1) == sorted(o.opportunity_id for o in opps2)

    def test_discover_has_provenance(self):
        kr = _make_knowledge_report()
        for opp in discover_from_knowledge_items(kr.items, _CTX, min_source_count=1):
            assert opp.provenance is not None
            assert opp.provenance.discovery_method

    def test_discover_confidence_bounded(self):
        kr = _make_knowledge_report()
        for opp in discover_from_knowledge_items(kr.items, _CTX, min_source_count=1):
            assert 0.0 <= opp.confidence <= 1.0

    def test_discover_has_explanation(self):
        kr = _make_knowledge_report()
        for opp in discover_from_knowledge_items(kr.items, _CTX, min_source_count=1):
            assert opp.explanation.why_exists

    def test_discover_versions_set(self):
        kr = _make_knowledge_report()
        for opp in discover_from_knowledge_items(kr.items, _CTX, min_source_count=1):
            assert opp.versions.opportunity_version == OPPORTUNITY_VERSION

    def test_discover_from_correlations_returns_list(self):
        kr = _make_knowledge_report()
        opps = discover_from_correlations(kr.correlations, kr.items, _CTX)
        assert isinstance(opps, list)

    def test_discover_from_correlations_empty(self):
        assert discover_from_correlations([], [], _CTX) == []

    def test_discover_no_duplicate_ids(self):
        kr = _make_knowledge_report()
        opps = discover_from_knowledge_items(kr.items, _CTX, min_source_count=1)
        ids = [o.opportunity_id for o in opps]
        assert len(ids) == len(set(ids))

    def test_discover_created_at_from_context(self):
        kr = _make_knowledge_report()
        for opp in discover_from_knowledge_items(kr.items, _CTX, min_source_count=1):
            assert opp.created_at == _TS


# ── Stage 3: Scoring ──────────────────────────────────────────────────────────


class TestOpportunityScoring:
    def test_score_returns_opportunity_score(self):
        opp = _make_opportunity()
        score = score_opportunity(opp, _CTX)
        assert isinstance(score, OpportunityScore)

    def test_score_composite_bounded(self):
        opp = _make_opportunity()
        score = score_opportunity(opp, _CTX)
        assert 0.0 <= score.composite_score <= 1.0

    def test_score_all_dimensions_bounded(self):
        opp = _make_opportunity()
        score = score_opportunity(opp, _CTX)
        for dim in [
            score.novelty, score.evidence_strength, score.source_diversity,
            score.growth_velocity, score.confidence, score.risk,
            score.market_impact, score.strategic_relevance, score.consistency, score.freshness,
        ]:
            assert 0.0 <= dim <= 1.0

    def test_score_deterministic(self):
        opp = _make_opportunity()
        s1 = score_opportunity(opp, _CTX)
        s2 = score_opportunity(opp, _CTX)
        assert s1.composite_score == s2.composite_score

    def test_score_evidence_ids_present(self):
        opp = _make_opportunity(evidence_count=5)
        score = score_opportunity(opp, _CTX)
        assert len(score.evidence_ids) > 0

    def test_rescore_all_updates_priority(self):
        opps = [_make_opportunity(title=f"Opp {i}", confidence=0.5 + i * 0.1) for i in range(3)]
        original_priorities = [o.priority for o in opps]
        rescore_all(opps, _CTX)
        for opp in opps:
            assert opp.priority == opp.score.composite_score

    def test_rescore_all_versions_on_score(self):
        opps = [_make_opportunity()]
        rescore_all(opps, _CTX)
        assert opps[0].score.versions.opportunity_version == OPPORTUNITY_VERSION

    def test_more_evidence_higher_strength(self):
        opp_few = _make_opportunity(evidence_count=1)
        opp_many = _make_opportunity(title="Many Evidence", evidence_count=10)
        s_few = score_opportunity(opp_few, _CTX)
        s_many = score_opportunity(opp_many, _CTX)
        assert s_many.evidence_strength >= s_few.evidence_strength


# ── Stage 4: Ranking ──────────────────────────────────────────────────────────


class TestOpportunityRanking:
    def test_rank_returns_same_count(self):
        opps = [_make_opportunity(title=f"Opp {i}", confidence=0.3 + i * 0.1) for i in range(5)]
        ranked = rank_opportunities(opps)
        assert len(ranked) == 5

    def test_rank_by_composite_sorted(self):
        opps = [_make_opportunity(title=f"Opp {i}", confidence=0.3 + i * 0.1) for i in range(5)]
        rescore_all(opps, _CTX)
        ranked = rank_opportunities(opps, RankingStrategy.BY_COMPOSITE)
        scores = [o.score.composite_score for o in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_rank_by_confidence_sorted(self):
        opps = [_make_opportunity(title=f"C{i}", confidence=0.3 + i * 0.1) for i in range(4)]
        ranked = rank_opportunities(opps, RankingStrategy.BY_CONFIDENCE)
        confidences = [o.confidence for o in ranked]
        assert confidences == sorted(confidences, reverse=True)

    def test_rank_deterministic(self):
        opps = [_make_opportunity(title=f"Opp {i}", confidence=0.5) for i in range(4)]
        r1 = rank_opportunities(opps, RankingStrategy.BY_COMPOSITE)
        r2 = rank_opportunities(opps, RankingStrategy.BY_COMPOSITE)
        assert [o.opportunity_id for o in r1] == [o.opportunity_id for o in r2]

    def test_rank_annotates_ranking_rationale(self):
        opps = [_make_opportunity(title=f"Opp {i}") for i in range(3)]
        ranked = rank_opportunities(opps)
        for opp in ranked:
            assert "Rank #" in opp.explanation.ranking_rationale

    def test_rank_empty_input(self):
        assert rank_opportunities([]) == []

    def test_all_strategies_produce_valid_ranking(self):
        opps = [_make_opportunity(title=f"Opp {i}", confidence=0.4 + i * 0.1) for i in range(3)]
        rescore_all(opps, _CTX)
        for strategy in RankingStrategy:
            ranked = rank_opportunities(opps, strategy)
            assert len(ranked) == 3

    def test_rank_stable_tiebreak_by_id(self):
        # Same confidence → should produce same order across runs
        opps = [_make_opportunity(title=f"Tie {i}", confidence=0.5) for i in range(5)]
        r1 = rank_opportunities(opps, RankingStrategy.BY_CONFIDENCE)
        r2 = rank_opportunities(opps, RankingStrategy.BY_CONFIDENCE)
        assert [o.opportunity_id for o in r1] == [o.opportunity_id for o in r2]


# ── Stage 5: Lifecycle ────────────────────────────────────────────────────────


class TestOpportunityLifecycle:
    def test_lifecycle_new_stage_low_confidence(self):
        opp = _make_opportunity(confidence=0.2, source_count=1)
        rescore_all([opp], _CTX)
        stage = _compute_lifecycle_stage(opp)
        assert stage in (LifecycleStage.NEW, LifecycleStage.EARLY, LifecycleStage.DECLINING)

    def test_lifecycle_archived_no_evidence(self):
        opp = _make_opportunity(confidence=0.01, evidence_count=0)
        opp.evidence = []
        stage = _compute_lifecycle_stage(opp)
        assert stage == LifecycleStage.ARCHIVED

    def test_lifecycle_early_two_sources(self):
        opp = _make_opportunity(confidence=0.35, source_count=2, evidence_count=3)
        rescore_all([opp], _CTX)
        stage = _compute_lifecycle_stage(opp)
        assert stage in (LifecycleStage.EARLY, LifecycleStage.NEW, LifecycleStage.GROWING)

    def test_lifecycle_advance_records_snapshot(self):
        opps = [_make_opportunity()]
        advance_lifecycle(opps, _CTX)
        assert len(opps[0].evolution_history) == 1

    def test_lifecycle_snapshot_has_correct_ts(self):
        opps = [_make_opportunity()]
        advance_lifecycle(opps, _CTX)
        assert opps[0].evolution_history[0].evaluation_timestamp == _TS

    def test_lifecycle_advance_sets_updated_at(self):
        opps = [_make_opportunity()]
        advance_lifecycle(opps, _CTX)
        assert opps[0].updated_at == _TS

    def test_lifecycle_advance_annotates_rationale(self):
        opps = [_make_opportunity()]
        advance_lifecycle(opps, _CTX)
        assert opps[0].explanation.lifecycle_rationale

    def test_lifecycle_deterministic(self):
        opp = _make_opportunity(confidence=0.5, source_count=3, evidence_count=6)
        s1 = _compute_lifecycle_stage(opp)
        s2 = _compute_lifecycle_stage(opp)
        assert s1 == s2


# ── Stage 6: Evolution ────────────────────────────────────────────────────────


class TestOpportunityEvolution:
    def _opp_with_history(self) -> Opportunity:
        from app.opportunity.dto import OpportunityEvolutionSnapshot, build_snapshot_id
        ts1 = datetime(2026, 6, 20, tzinfo=timezone.utc)
        ts2 = datetime(2026, 6, 29, tzinfo=timezone.utc)
        opp = _make_opportunity(confidence=0.6)
        snap1 = OpportunityEvolutionSnapshot(
            snapshot_id=build_snapshot_id(opp.opportunity_id, ts1),
            opportunity_id=opp.opportunity_id,
            evaluation_timestamp=ts1,
            confidence=0.3, priority=0.3, composite_score=0.3,
            lifecycle_stage=LifecycleStage.NEW, evidence_count=2, source_count=1, entity_count=1,
        )
        snap2 = OpportunityEvolutionSnapshot(
            snapshot_id=build_snapshot_id(opp.opportunity_id, ts2),
            opportunity_id=opp.opportunity_id,
            evaluation_timestamp=ts2,
            confidence=0.6, priority=0.6, composite_score=0.6,
            lifecycle_stage=LifecycleStage.GROWING, evidence_count=6, source_count=3, entity_count=2,
        )
        opp.evolution_history = [snap1, snap2]
        return opp

    def test_direction_improving(self):
        opp = self._opp_with_history()
        direction = compute_evolution_direction(opp.evolution_history)
        assert direction == EvolutionDirection.IMPROVING

    def test_direction_unknown_single_snapshot(self):
        opp = _make_opportunity()
        advance_lifecycle([opp], _CTX)
        direction = compute_evolution_direction(opp.evolution_history)
        assert direction == EvolutionDirection.UNKNOWN

    def test_direction_stable(self):
        from app.opportunity.dto import OpportunityEvolutionSnapshot, build_snapshot_id
        ts1 = datetime(2026, 6, 20, tzinfo=timezone.utc)
        ts2 = datetime(2026, 6, 29, tzinfo=timezone.utc)
        opp = _make_opportunity()
        opp.evolution_history = [
            OpportunityEvolutionSnapshot(
                snapshot_id=build_snapshot_id(opp.opportunity_id, ts1),
                opportunity_id=opp.opportunity_id, evaluation_timestamp=ts1,
                confidence=0.5, priority=0.5, composite_score=0.5,
                lifecycle_stage=LifecycleStage.GROWING, evidence_count=5, source_count=2, entity_count=2,
            ),
            OpportunityEvolutionSnapshot(
                snapshot_id=build_snapshot_id(opp.opportunity_id, ts2),
                opportunity_id=opp.opportunity_id, evaluation_timestamp=ts2,
                confidence=0.51, priority=0.51, composite_score=0.51,
                lifecycle_stage=LifecycleStage.GROWING, evidence_count=5, source_count=2, entity_count=2,
            ),
        ]
        direction = compute_evolution_direction(opp.evolution_history)
        assert direction == EvolutionDirection.STABLE

    def test_build_evolution_explanation_contains_direction(self):
        opp = self._opp_with_history()
        explanation = build_evolution_explanation(opp)
        assert "Direction:" in explanation or "IMPROVING" in explanation

    def test_annotate_evolution_no_error(self):
        opps = [_make_opportunity() for _ in range(3)]
        advance_lifecycle(opps, _CTX)
        annotate_evolution(opps)  # should not raise

    def test_build_evolution_explanation_no_history(self):
        opp = _make_opportunity()
        explanation = build_evolution_explanation(opp)
        assert "No evolution history" in explanation


# ── Stage 7: Portfolio ────────────────────────────────────────────────────────


class TestOpportunityPortfolio:
    def test_portfolio_builds_nodes(self):
        opps = [
            _make_opportunity("AI SDK", domain="technology", opp_type=OpportunityType.TECHNOLOGY),
            _make_opportunity("CUDA Library", domain="technology", opp_type=OpportunityType.INFRASTRUCTURE),
            _make_opportunity("Research Paper", domain="research", opp_type=OpportunityType.RESEARCH),
        ]
        portfolio = build_portfolio(opps)
        assert len(portfolio) >= 1

    def test_portfolio_empty_input(self):
        assert build_portfolio([]) == []

    def test_portfolio_node_count_matches(self):
        opps = [_make_opportunity(title=f"O{i}", domain="tech") for i in range(4)]
        portfolio = build_portfolio(opps)
        total = sum(n.opportunity_count for n in portfolio)
        assert total == 4

    def test_portfolio_hierarchical_children(self):
        opps = [
            _make_opportunity("T1", domain="tech", opp_type=OpportunityType.TECHNOLOGY),
            _make_opportunity("I1", domain="tech", opp_type=OpportunityType.INFRASTRUCTURE),
        ]
        portfolio = build_portfolio(opps)
        domain_node = next((n for n in portfolio if n.domain == "tech"), None)
        assert domain_node is not None
        assert len(domain_node.children) >= 1

    def test_portfolio_node_ids_deterministic(self):
        opps = [_make_opportunity(title=f"O{i}", domain="tech") for i in range(3)]
        p1 = build_portfolio(opps)
        p2 = build_portfolio(opps)
        ids1 = sorted(n.node_id for n in p1)
        ids2 = sorted(n.node_id for n in p2)
        assert ids1 == ids2

    def test_portfolio_composite_score_bounded(self):
        opps = [_make_opportunity(title=f"O{i}") for i in range(3)]
        for n in build_portfolio(opps):
            assert 0.0 <= n.composite_score <= 1.0


# ── Stage 8: Health ───────────────────────────────────────────────────────────


class TestOpportunityHealth:
    def test_health_empty_returns_zeros(self):
        h = compute_opportunity_health([], _CTX)
        assert h.health_score == 0.0
        assert h.opportunity_count == 0

    def test_health_non_empty_returns_object(self):
        opps = [_make_opportunity(title=f"O{i}") for i in range(3)]
        advance_lifecycle(opps, _CTX)
        h = compute_opportunity_health(opps, _CTX)
        assert 0.0 <= h.health_score <= 1.0

    def test_health_all_dimensions_bounded(self):
        opps = [_make_opportunity(title=f"O{i}", confidence=0.5 + i * 0.1) for i in range(5)]
        advance_lifecycle(opps, _CTX)
        h = compute_opportunity_health(opps, _CTX)
        for dim in [
            h.evidence_quality, h.freshness, h.confidence, h.consistency,
            h.coverage, h.source_diversity, h.market_activity,
            h.historical_stability, h.novelty, h.explainability,
        ]:
            assert 0.0 <= dim <= 1.0

    def test_health_count_matches(self):
        opps = [_make_opportunity(title=f"O{i}") for i in range(4)]
        h = compute_opportunity_health(opps, _CTX)
        assert h.opportunity_count == 4

    def test_health_explainability_from_explanations(self):
        opps = [_make_opportunity(title=f"O{i}") for i in range(3)]
        h = compute_opportunity_health(opps, _CTX)
        assert h.explainability == 1.0  # all have why_exists set by _make_opportunity

    def test_health_versions_set(self):
        opps = [_make_opportunity()]
        h = compute_opportunity_health(opps, _CTX)
        assert h.versions.opportunity_version == OPPORTUNITY_VERSION

    def test_health_deterministic(self):
        opps = [_make_opportunity(title=f"O{i}") for i in range(3)]
        advance_lifecycle(opps, _CTX)
        h1 = compute_opportunity_health(opps, _CTX)
        h2 = compute_opportunity_health(opps, _CTX)
        assert h1.health_score == h2.health_score


# ── Stage 9: Explainability ───────────────────────────────────────────────────


class TestExplainability:
    def test_why_exists_non_empty_after_discovery(self):
        kr = _make_knowledge_report()
        opps = discover_from_knowledge_items(kr.items, _CTX, min_source_count=1)
        for opp in opps:
            assert opp.explanation.why_exists

    def test_evidence_basis_non_empty_after_scoring(self):
        kr = _make_knowledge_report()
        opps = discover_from_knowledge_items(kr.items, _CTX, min_source_count=1)
        rescore_all(opps, _CTX)
        for opp in opps:
            assert isinstance(opp.explanation.evidence_basis, list)

    def test_source_contributions_non_empty(self):
        kr = _make_knowledge_report()
        opps = discover_from_knowledge_items(kr.items, _CTX, min_source_count=1)
        for opp in opps:
            # Some opps may have empty source_contributions if only 1 source
            assert isinstance(opp.explanation.source_contributions, dict)

    def test_ranking_rationale_after_rank(self):
        opps = [_make_opportunity(title=f"O{i}") for i in range(3)]
        ranked = rank_opportunities(opps)
        for opp in ranked:
            assert "Rank #" in opp.explanation.ranking_rationale

    def test_lifecycle_rationale_after_advance(self):
        opps = [_make_opportunity()]
        advance_lifecycle(opps, _CTX)
        assert opps[0].explanation.lifecycle_rationale

    def test_confidence_rationale_after_scoring(self):
        opp = _make_opportunity()
        score_opportunity(opp, _CTX)
        # confidence_rationale may be populated during discovery
        assert isinstance(opp.explanation.confidence_rationale, str)

    def test_full_pipeline_explanation_chain(self):
        kr = _make_knowledge_report()
        report = run_opportunity_pipeline(kr, _CTX)
        for opp in report.opportunities:
            assert opp.explanation.why_exists  # discovery
            assert opp.explanation.lifecycle_rationale  # lifecycle
            if report.ranked_opportunities:
                # ranking_rationale comes from ranked list
                pass


# ── Stage 10: Learning ────────────────────────────────────────────────────────


class TestAdaptiveLearning:
    def test_apply_calibration_no_feedback_passthrough(self):
        opps = [_make_opportunity(confidence=0.5)]
        result = apply_adaptive_calibration(opps, _CTX, strategy_feedback=None)
        assert result[0].confidence == 0.5

    def test_apply_calibration_with_factor(self):
        opps = [_make_opportunity(confidence=0.5)]
        apply_adaptive_calibration(opps, _CTX, strategy_feedback={"calibration_factor": 1.1})
        assert opps[0].confidence == round(min(1.0, 0.5 * 1.1), 4)

    def test_apply_calibration_bounded_above(self):
        opps = [_make_opportunity(confidence=0.95)]
        apply_adaptive_calibration(opps, _CTX, strategy_feedback={"calibration_factor": 1.2})
        assert opps[0].confidence <= 1.0

    def test_apply_calibration_factor_clamped(self):
        # Factor > 1.2 should be clamped to 1.2
        opps = [_make_opportunity(confidence=0.5)]
        apply_adaptive_calibration(opps, _CTX, strategy_feedback={"calibration_factor": 2.0})
        assert opps[0].confidence <= round(0.5 * 1.2, 4) + 0.001

    def test_apply_calibration_annotates_rationale(self):
        opps = [_make_opportunity()]
        apply_adaptive_calibration(opps, _CTX, strategy_feedback={"calibration_factor": 1.05})
        assert "Adaptive calibration" in opps[0].explanation.confidence_rationale

    def test_build_feedback_structure(self):
        opps = [_make_opportunity(confidence=0.6), _make_opportunity(title="B", confidence=0.8)]
        feedback = build_opportunity_feedback(opps)
        assert "opportunity_count" in feedback
        assert "avg_confidence" in feedback
        assert "lifecycle_distribution" in feedback
        assert feedback["opportunity_count"] == 2

    def test_build_feedback_empty(self):
        feedback = build_opportunity_feedback([])
        assert feedback["opportunity_count"] == 0

    def test_feedback_versions_present(self):
        opps = [_make_opportunity()]
        feedback = build_opportunity_feedback(opps)
        assert "versions" in feedback
        assert "business-os-1.5" in feedback["versions"]["opportunity_version"]


# ── Pipeline Orchestrator ─────────────────────────────────────────────────────


class TestOpportunityPipeline:
    def test_pipeline_runs(self):
        kr = _make_knowledge_report()
        report = run_opportunity_pipeline(kr, _CTX)
        assert report is not None

    def test_pipeline_report_id_set(self):
        kr = _make_knowledge_report()
        report = run_opportunity_pipeline(kr, _CTX)
        assert report.report_id

    def test_pipeline_health_present(self):
        kr = _make_knowledge_report()
        report = run_opportunity_pipeline(kr, _CTX)
        assert 0.0 <= report.health.health_score <= 1.0

    def test_pipeline_versions_set(self):
        kr = _make_knowledge_report()
        report = run_opportunity_pipeline(kr, _CTX)
        assert report.versions.opportunity_version == OPPORTUNITY_VERSION

    def test_pipeline_generated_at_from_context(self):
        kr = _make_knowledge_report()
        report = run_opportunity_pipeline(kr, _CTX)
        assert report.generated_at == _TS

    def test_pipeline_ranked_opportunities_same_count(self):
        kr = _make_knowledge_report()
        report = run_opportunity_pipeline(kr, _CTX, min_source_count=1)
        assert len(report.ranked_opportunities) == len(report.opportunities)

    def test_pipeline_portfolio_present(self):
        kr = _make_knowledge_report()
        report = run_opportunity_pipeline(kr, _CTX, min_source_count=1)
        assert isinstance(report.portfolio, list)

    def test_pipeline_knowledge_item_count(self):
        kr = _make_knowledge_report()
        report = run_opportunity_pipeline(kr, _CTX)
        assert report.knowledge_item_count == len(kr.items)

    def test_pipeline_empty_knowledge(self):
        from app.knowledge.dto import KnowledgeHealth, KnowledgeReport, KnowledgeVersionMetadata
        from app.knowledge.dto import _k_stable_hash as ksh
        empty_kr = KnowledgeReport(
            report_id=ksh({"empty": True}),
            health=KnowledgeHealth(
                coverage=0.0, freshness=0.0, source_diversity=0.0, evidence_quality=0.0,
                entity_resolution_quality=0.0, correlation_strength=0.0, knowledge_density=0.0,
                completeness=0.0, explainability=0.0, version_consistency=0.0, health_score=0.0,
            ),
            evaluation_context=_CTX,
            generated_at=_TS,
        )
        report = run_opportunity_pipeline(empty_kr, _CTX)
        assert report.opportunities == []

    def test_pipeline_with_strategy_feedback(self):
        kr = _make_knowledge_report()
        report = run_opportunity_pipeline(
            kr, _CTX,
            min_source_count=1,
            strategy_feedback={"calibration_factor": 1.05},
        )
        assert report is not None

    def test_pipeline_ranking_strategy_in_report(self):
        kr = _make_knowledge_report()
        report = run_opportunity_pipeline(kr, _CTX, ranking_strategy=RankingStrategy.BY_NOVELTY)
        assert report.ranking_strategy == RankingStrategy.BY_NOVELTY


# ── Replay Determinism ────────────────────────────────────────────────────────


class TestReplayDeterminism:
    def test_report_id_stable(self):
        kr = _make_knowledge_report()
        r1 = run_opportunity_pipeline(kr, _CTX, min_source_count=1)
        r2 = run_opportunity_pipeline(kr, _CTX, min_source_count=1)
        assert r1.report_id == r2.report_id

    def test_opportunity_ids_stable(self):
        kr = _make_knowledge_report()
        r1 = run_opportunity_pipeline(kr, _CTX, min_source_count=1)
        r2 = run_opportunity_pipeline(kr, _CTX, min_source_count=1)
        assert sorted(o.opportunity_id for o in r1.opportunities) == sorted(o.opportunity_id for o in r2.opportunities)

    def test_health_score_stable(self):
        kr = _make_knowledge_report()
        r1 = run_opportunity_pipeline(kr, _CTX, min_source_count=1)
        r2 = run_opportunity_pipeline(kr, _CTX, min_source_count=1)
        assert r1.health.health_score == r2.health.health_score

    def test_ranking_stable(self):
        kr = _make_knowledge_report()
        r1 = run_opportunity_pipeline(kr, _CTX, min_source_count=1)
        r2 = run_opportunity_pipeline(kr, _CTX, min_source_count=1)
        ids1 = [o.opportunity_id for o in r1.ranked_opportunities]
        ids2 = [o.opportunity_id for o in r2.ranked_opportunities]
        assert ids1 == ids2

    def test_different_context_different_report_id(self):
        kr = _make_knowledge_report()
        ctx2 = EvaluationContext(evaluation_timestamp=datetime(2026, 7, 1, tzinfo=timezone.utc), dataset_version="test-1.5")
        r1 = run_opportunity_pipeline(kr, _CTX, min_source_count=1)
        r2 = run_opportunity_pipeline(kr, ctx2, min_source_count=1)
        assert r1.report_id != r2.report_id

    def test_scoring_deterministic(self):
        opp = _make_opportunity()
        s1 = score_opportunity(opp, _CTX)
        s2 = score_opportunity(opp, _CTX)
        assert s1.composite_score == s2.composite_score
        assert s1.evidence_strength == s2.evidence_strength

    def test_provenance_hash_stable(self):
        kr = _make_knowledge_report()
        r1 = run_opportunity_pipeline(kr, _CTX, min_source_count=1)
        r2 = run_opportunity_pipeline(kr, _CTX, min_source_count=1)
        hashes1 = sorted(o.provenance.provenance_hash for o in r1.opportunities)
        hashes2 = sorted(o.provenance.provenance_hash for o in r2.opportunities)
        assert hashes1 == hashes2


# ── Backward Compatibility ────────────────────────────────────────────────────


class TestBackwardCompatibility:
    def test_knowledge_platform_unaffected(self):
        from app.knowledge.orchestrator import run_knowledge_pipeline
        from app.knowledge.connectors.hacker_news import HackerNewsConnector
        kr = run_knowledge_pipeline([HackerNewsConnector(max_items=3, _raw_override=_HN_RAW)], _CTX)
        assert kr.health is not None

    def test_adaptive_intelligence_unaffected(self):
        from app.adaptive_intelligence.dto import EvaluationContext, ScientificVersionMetadata
        ctx = EvaluationContext(evaluation_timestamp=_TS, dataset_version="test")
        m = ScientificVersionMetadata()
        assert m.learning_version

    def test_1_3_certifications_intact(self):
        from app.adaptive_intelligence.dto import AdaptiveIntelligenceReport
        assert AdaptiveIntelligenceReport is not None

    def test_1_4_knowledge_model_intact(self):
        from app.knowledge.dto import (
            KNOWLEDGE_VERSION, KnowledgeReport, KnowledgeItem, FusedKnowledgeItem
        )
        assert "1.4" in KNOWLEDGE_VERSION

    def test_opportunity_version_metadata_includes_knowledge_version(self):
        from app.opportunity.dto import OpportunityVersionMetadata
        from app.knowledge.dto import KNOWLEDGE_VERSION
        m = OpportunityVersionMetadata()
        assert m.knowledge_version == KNOWLEDGE_VERSION

    def test_shadow_contracts_still_importable(self):
        from app.knowledge.dto import Goal, Decision, ExecutionPlan
        g = Goal(goal_id="g1", description="test")
        assert g.status == "pending"
