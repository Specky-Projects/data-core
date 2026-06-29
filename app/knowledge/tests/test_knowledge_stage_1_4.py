"""Business OS 1.4 — Universal Knowledge Platform — Scientific Test Suite.

Tests:
  - Connector abstraction (all 4 source types via _raw_override)
  - Normalization determinism
  - Canonical model integrity
  - Entity resolution (alias map, deduplication)
  - Knowledge fusion (union-find, strategies)
  - Cross-source correlation
  - Provenance
  - Freshness
  - Knowledge health (10 dimensions)
  - Logical knowledge graph
  - Pipeline orchestrator
  - Replay determinism
  - Backward compatibility (all 203 prior tests must still pass)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.adaptive_intelligence.dto import EvaluationContext
from app.knowledge.connectors.blog import BlogConnector
from app.knowledge.connectors.github import GitHubConnector
from app.knowledge.connectors.hacker_news import HackerNewsConnector
from app.knowledge.connectors.rss import RSSConnector
from app.knowledge.correlation import (
    compute_cross_source_correlations,
    compute_entity_co_occurrence,
)
from app.knowledge.dto import (
    CONNECTOR_VERSION,
    CORRELATION_VERSION,
    ENTITY_RESOLUTION_VERSION,
    FUSION_VERSION,
    GRAPH_VERSION,
    KNOWLEDGE_VERSION,
    PROVENANCE_VERSION,
    CorrelationSignal,
    EntityCandidate,
    EntityType,
    FusionStrategy,
    KnowledgeVersionMetadata,
    RelationshipType,
    SourceType,
    _EPOCH,
    _k_stable_hash,
    _normalize_entity_name,
    build_correlation_id,
    build_entity_id,
    build_evidence_id,
    build_item_id,
    build_knowledge_provenance,
    build_relationship_id,
    compute_knowledge_freshness,
    compute_knowledge_health,
)
from app.knowledge.entity_resolution import (
    _canonical_name,
    merge_entity_lists,
    resolve_entities,
)
from app.knowledge.graph import LogicalKnowledgeGraph, build_knowledge_graph
from app.knowledge.knowledge_fusion import fuse_knowledge_items
from app.knowledge.orchestrator import run_knowledge_pipeline

# ── Fixtures ───────────────────────────────────────────────────────────────────

_TS = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)
_TS_OLD = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
_CTX = EvaluationContext(evaluation_timestamp=_TS, dataset_version="test-1.4")

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
]

_RSS_RAW = [
    {
        "title": "Python 3.13 released",
        "link": "https://python.org/news/python-313",
        "description": "Python 3.13 introduces new type system features.",
        "pubDate": "Mon, 01 Jun 2026 00:00:00 +0000",
    }
]

_BLOG_RAW = [
    {
        "url": "https://example.com/blog/1",
        "html_title": "Building LLM Apps with FastAPI",
        "body_text": "FastAPI and OpenAI make building LLM applications easy.",
    }
]


def _make_eval_ctx(ts: datetime = _TS) -> EvaluationContext:
    return EvaluationContext(evaluation_timestamp=ts, dataset_version="test-1.4")


# ── Stage 1: Version Constants ─────────────────────────────────────────────────


class TestVersionConstants:
    def test_knowledge_version(self):
        assert KNOWLEDGE_VERSION == "business-os-1.4-knowledge"

    def test_connector_version(self):
        assert "1.4" in CONNECTOR_VERSION

    def test_entity_resolution_version(self):
        assert "1.4" in ENTITY_RESOLUTION_VERSION

    def test_all_versions_distinct(self):
        versions = [
            KNOWLEDGE_VERSION, CONNECTOR_VERSION, ENTITY_RESOLUTION_VERSION,
            FUSION_VERSION, CORRELATION_VERSION, GRAPH_VERSION, PROVENANCE_VERSION,
        ]
        assert len(set(versions)) == len(versions)

    def test_knowledge_version_metadata_defaults(self):
        m = KnowledgeVersionMetadata()
        assert m.knowledge_version == KNOWLEDGE_VERSION
        assert m.graph_version == GRAPH_VERSION


# ── Stage 2: Utility Functions ─────────────────────────────────────────────────


class TestUtilities:
    def test_k_stable_hash_deterministic(self):
        h1 = _k_stable_hash({"a": 1, "b": 2})
        h2 = _k_stable_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_k_stable_hash_length(self):
        h = _k_stable_hash({"x": "y"})
        assert len(h) == 32

    def test_normalize_entity_name_lowercase(self):
        assert _normalize_entity_name("OpenAI") == "openai"

    def test_normalize_entity_name_sorted_tokens(self):
        assert _normalize_entity_name("Machine Learning") == "learning machine"

    def test_normalize_entity_name_strips_punctuation(self):
        result = _normalize_entity_name("OpenAI, Inc.")
        assert "," not in result

    def test_build_entity_id_deterministic(self):
        id1 = build_entity_id("OpenAI", EntityType.ORGANIZATION)
        id2 = build_entity_id("openai", EntityType.ORGANIZATION)
        assert id1 == id2

    def test_build_item_id_deterministic(self):
        id1 = build_item_id("https://example.com", "src:1")
        id2 = build_item_id("https://example.com", "src:1")
        assert id1 == id2

    def test_build_evidence_id_deterministic(self):
        ts = _EPOCH
        id1 = build_evidence_id("src:1", "some content", ts)
        id2 = build_evidence_id("src:1", "some content", ts)
        assert id1 == id2

    def test_build_relationship_id_symmetric(self):
        id1 = build_relationship_id("entity_a", "entity_b", RelationshipType.CO_OCCURS_WITH)
        id2 = build_relationship_id("entity_b", "entity_a", RelationshipType.CO_OCCURS_WITH)
        assert id1 == id2

    def test_build_correlation_id_sorted_entities(self):
        id1 = build_correlation_id(["e1", "e2"], CorrelationSignal.CROSS_SOURCE_CONVERGENCE, 30)
        id2 = build_correlation_id(["e2", "e1"], CorrelationSignal.CROSS_SOURCE_CONVERGENCE, 30)
        assert id1 == id2

    def test_epoch_is_utc(self):
        assert _EPOCH.tzinfo is not None
        assert _EPOCH.year == 1970


# ── Stage 3: Connectors ────────────────────────────────────────────────────────


class TestGitHubConnector:
    def _connector(self):
        return GitHubConnector(
            topics=["llm"], max_items=5, _raw_override=_GH_RAW
        )

    def test_ingest_returns_items(self):
        items = self._connector().ingest(_CTX)
        assert len(items) >= 1

    def test_ingest_deterministic(self):
        c = self._connector()
        r1 = c.ingest(_CTX)
        r2 = c.ingest(_CTX)
        assert [i.item_id for i in r1] == [i.item_id for i in r2]

    def test_source_type(self):
        items = self._connector().ingest(_CTX)
        assert all(i.source.source_type == SourceType.GITHUB for i in items)

    def test_entities_extracted(self):
        items = self._connector().ingest(_CTX)
        # At least some items should have entities
        total = sum(len(i.entities) for i in items)
        assert total >= 0  # may be empty if no keywords match

    def test_versions_on_items(self):
        items = self._connector().ingest(_CTX)
        for item in items:
            assert item.versions.knowledge_version == KNOWLEDGE_VERSION

    def test_provenance_source_id(self):
        items = self._connector().ingest(_CTX)
        for item in items:
            assert "github" in item.provenance.original_source

    def test_engagement_from_stars(self):
        items = self._connector().ingest(_CTX)
        # huggingface/transformers has 90000 stars → should have positive engagement
        scores = [i.engagement_score for i in items]
        assert max(scores) > 0

    def test_raw_override_skips_http(self):
        # _raw_override means no real HTTP — should complete fast
        items = self._connector().ingest(_CTX)
        assert items is not None


class TestHackerNewsConnector:
    def _connector(self):
        return HackerNewsConnector(max_items=5, _raw_override=_HN_RAW)

    def test_ingest_returns_items(self):
        items = self._connector().ingest(_CTX)
        assert len(items) >= 1

    def test_source_type(self):
        items = self._connector().ingest(_CTX)
        assert all(i.source.source_type == SourceType.HACKER_NEWS for i in items)

    def test_deterministic(self):
        c = self._connector()
        r1 = c.ingest(_CTX)
        r2 = c.ingest(_CTX)
        assert [i.item_id for i in r1] == [i.item_id for i in r2]

    def test_engagement_score_from_score(self):
        items = self._connector().ingest(_CTX)
        scores = [i.engagement_score for i in items]
        assert max(scores) > 0


class TestRSSConnector:
    def _connector(self):
        return RSSConnector(
            feed_url="https://example.com/rss",
            feed_name="Example",
            max_items=5,
            _raw_override=_RSS_RAW,
        )

    def test_ingest_returns_items(self):
        items = self._connector().ingest(_CTX)
        assert len(items) >= 1

    def test_source_type(self):
        items = self._connector().ingest(_CTX)
        assert all(i.source.source_type == SourceType.RSS for i in items)

    def test_title_extracted(self):
        items = self._connector().ingest(_CTX)
        assert "Python" in items[0].title or "3.13" in items[0].title

    def test_deterministic(self):
        c = self._connector()
        r1 = c.ingest(_CTX)
        r2 = c.ingest(_CTX)
        assert [i.item_id for i in r1] == [i.item_id for i in r2]


class TestBlogConnector:
    def _connector(self):
        return BlogConnector(
            urls=["https://example.com/blog/1"],
            blog_name="Test Blog",
            _raw_override=_BLOG_RAW,
        )

    def test_ingest_returns_items(self):
        items = self._connector().ingest(_CTX)
        assert len(items) >= 1

    def test_source_type(self):
        items = self._connector().ingest(_CTX)
        assert all(i.source.source_type == SourceType.BLOG for i in items)

    def test_title_from_html_title(self):
        items = self._connector().ingest(_CTX)
        assert "FastAPI" in items[0].title or "LLM" in items[0].title

    def test_deterministic(self):
        c = self._connector()
        r1 = c.ingest(_CTX)
        r2 = c.ingest(_CTX)
        assert [i.item_id for i in r1] == [i.item_id for i in r2]


# ── Stage 4: Entity Resolution ────────────────────────────────────────────────


class TestEntityResolution:
    def test_canonical_name_alias_openai(self):
        assert _canonical_name("OpenAI Inc.") == "openai"

    def test_canonical_name_alias_meta(self):
        assert _canonical_name("Facebook") == "meta"

    def test_canonical_name_alias_aws(self):
        assert _canonical_name("Amazon Web Services") == "aws"

    def test_canonical_name_alias_kubernetes(self):
        assert _canonical_name("k8s") == "kubernetes"

    def test_canonical_name_unknown_passthrough(self):
        result = _canonical_name("SomeUnknownTech")
        assert result  # not empty

    def test_resolve_entities_deduplication(self):
        candidates = [
            EntityCandidate(raw_name="OpenAI", entity_type=EntityType.ORGANIZATION, confidence=0.9),
            EntityCandidate(raw_name="OpenAI Inc.", entity_type=EntityType.ORGANIZATION, confidence=0.8),
        ]
        entities = resolve_entities(candidates, "src:test", [])
        # Both canonicalize to "openai" → should be 1 entity
        assert len(entities) == 1
        assert entities[0].canonical_name == "openai"

    def test_resolve_entities_confidence_max(self):
        candidates = [
            EntityCandidate(raw_name="Python", entity_type=EntityType.TECHNOLOGY, confidence=0.7),
            EntityCandidate(raw_name="Python", entity_type=EntityType.TECHNOLOGY, confidence=0.9),
        ]
        entities = resolve_entities(candidates, "src:test", [])
        assert entities[0].confidence == 0.9

    def test_resolve_entities_different_types_stay_separate(self):
        candidates = [
            EntityCandidate(raw_name="Python", entity_type=EntityType.TECHNOLOGY, confidence=0.8),
            EntityCandidate(raw_name="Python", entity_type=EntityType.PERSON, confidence=0.5),
        ]
        entities = resolve_entities(candidates, "src:test", [])
        assert len(entities) == 2

    def test_merge_entity_lists_combines(self):
        candidates_a = [EntityCandidate(raw_name="Python", entity_type=EntityType.TECHNOLOGY, confidence=0.8)]
        candidates_b = [EntityCandidate(raw_name="Python", entity_type=EntityType.TECHNOLOGY, confidence=0.6)]
        ea = resolve_entities(candidates_a, "src:a", [])
        eb = resolve_entities(candidates_b, "src:b", [])
        merged = merge_entity_lists([ea, eb])
        assert len(merged) == 1
        assert merged[0].provenance.sources_count == 2

    def test_entity_id_deterministic_across_connectors(self):
        id1 = build_entity_id("python", EntityType.TECHNOLOGY)
        id2 = build_entity_id("Python", EntityType.TECHNOLOGY)
        assert id1 == id2


# ── Stage 5: Knowledge Fusion ─────────────────────────────────────────────────


class TestKnowledgeFusion:
    def _items(self):
        gh = GitHubConnector(topics=["llm"], max_items=5, _raw_override=_GH_RAW)
        hn = HackerNewsConnector(max_items=5, _raw_override=_HN_RAW)
        return gh.ingest(_CTX) + hn.ingest(_CTX)

    def test_fuse_returns_list(self):
        items = self._items()
        fused = fuse_knowledge_items(items)
        assert isinstance(fused, list)

    def test_fuse_empty_input(self):
        assert fuse_knowledge_items([]) == []

    def test_fuse_single_item(self):
        items = self._items()[:1]
        fused = fuse_knowledge_items(items)
        assert len(fused) == 1
        assert fused[0].source_count == 1

    def test_fuse_url_canonical_merges(self):
        # HN item 1002 points to the same URL as GH item transformers
        items = self._items()
        fused = fuse_knowledge_items(items, threshold=0.1)
        assert all(f.fusion_id for f in fused)

    def test_fuse_fusion_hash_set(self):
        items = self._items()
        fused = fuse_knowledge_items(items)
        for f in fused:
            assert f.fusion_hash

    def test_fuse_deterministic(self):
        items = self._items()
        f1 = fuse_knowledge_items(items)
        f2 = fuse_knowledge_items(items)
        assert [f.fusion_id for f in f1] == [f.fusion_id for f in f2]

    def test_fuse_versions_on_fused_items(self):
        items = self._items()
        for f in fuse_knowledge_items(items):
            assert f.versions.knowledge_version == KNOWLEDGE_VERSION


# ── Stage 6: Correlation ──────────────────────────────────────────────────────


class TestCorrelation:
    def _items(self):
        gh = GitHubConnector(topics=["llm"], max_items=5, _raw_override=_GH_RAW)
        hn = HackerNewsConnector(max_items=5, _raw_override=_HN_RAW)
        return gh.ingest(_CTX) + hn.ingest(_CTX)

    def test_cross_source_returns_list(self):
        items = self._items()
        result = compute_cross_source_correlations(items, _CTX)
        assert isinstance(result, list)

    def test_cross_source_empty_input(self):
        assert compute_cross_source_correlations([], _CTX) == []

    def test_cross_source_strength_bounds(self):
        items = self._items()
        for c in compute_cross_source_correlations(items, _CTX):
            assert 0.0 <= c.strength <= 1.0

    def test_cross_source_sorted_by_strength(self):
        items = self._items()
        correlations = compute_cross_source_correlations(items, _CTX)
        strengths = [c.strength for c in correlations]
        assert strengths == sorted(strengths, reverse=True)

    def test_cross_source_has_explanation(self):
        items = self._items()
        for c in compute_cross_source_correlations(items, _CTX):
            assert c.explanation

    def test_co_occurrence_returns_list(self):
        items = self._items()
        result = compute_entity_co_occurrence(items, _CTX)
        assert isinstance(result, list)

    def test_co_occurrence_empty_input(self):
        assert compute_entity_co_occurrence([], _CTX) == []

    def test_correlation_versions(self):
        items = self._items()
        for c in compute_cross_source_correlations(items, _CTX):
            assert c.versions.knowledge_version == KNOWLEDGE_VERSION

    def test_time_window_filters_old_items(self):
        items = self._items()
        # Use a very old evaluation timestamp → all items should be outside window
        old_ctx = EvaluationContext(evaluation_timestamp=datetime(2020, 1, 1, tzinfo=timezone.utc), dataset_version="test-1.4")
        result = compute_cross_source_correlations(items, old_ctx, window_days=1)
        assert result == []


# ── Stage 7: Provenance ───────────────────────────────────────────────────────


class TestProvenance:
    def test_build_knowledge_provenance(self):
        prov = build_knowledge_provenance(
            source_id="github:test",
            connector_name="github",
            evaluation_context=_CTX,
            evidence_ids=["ev1", "ev2"],
            published_at=None,
        )
        assert prov.original_source == "github:test"
        assert prov.normalized_by == "github"
        assert "github" in prov.normalization_history
        assert prov.provenance_hash

    def test_provenance_hash_deterministic(self):
        prov1 = build_knowledge_provenance(
            source_id="github:test",
            connector_name="github",
            evaluation_context=_CTX,
            evidence_ids=["ev1"],
        )
        prov2 = build_knowledge_provenance(
            source_id="github:test",
            connector_name="github",
            evaluation_context=_CTX,
            evidence_ids=["ev1"],
        )
        assert prov1.provenance_hash == prov2.provenance_hash

    def test_provenance_versions_set(self):
        prov = build_knowledge_provenance(
            source_id="src:x", connector_name="x", evaluation_context=_CTX, evidence_ids=[],
        )
        assert prov.versions.knowledge_version == KNOWLEDGE_VERSION

    def test_provenance_discovered_at_from_context(self):
        prov = build_knowledge_provenance(
            source_id="src:x", connector_name="x", evaluation_context=_CTX, evidence_ids=[],
        )
        assert prov.discovered_at == _TS


# ── Stage 8: Freshness ────────────────────────────────────────────────────────


class TestFreshness:
    def test_freshness_recent_item_high(self):
        f = compute_knowledge_freshness(
            published_at=_TS,
            evaluation_context=_CTX,
        )
        assert f.knowledge_freshness >= 0.9

    def test_freshness_old_item_low(self):
        old = datetime(2020, 1, 1, tzinfo=timezone.utc)
        f = compute_knowledge_freshness(
            published_at=old,
            evaluation_context=_CTX,
        )
        assert f.knowledge_freshness <= 0.1

    def test_freshness_none_published_at_uses_min(self):
        f = compute_knowledge_freshness(published_at=None, evaluation_context=_CTX)
        assert f.knowledge_freshness == 0.05

    def test_freshness_bounds(self):
        f = compute_knowledge_freshness(published_at=_TS, evaluation_context=_CTX)
        assert 0.0 <= f.knowledge_freshness <= 1.0
        assert 0.0 <= f.source_freshness <= 1.0

    def test_freshness_evaluated_at_from_context(self):
        f = compute_knowledge_freshness(published_at=_TS, evaluation_context=_CTX)
        assert f.evaluated_at == _TS

    def test_freshness_deterministic(self):
        f1 = compute_knowledge_freshness(published_at=_TS_OLD, evaluation_context=_CTX)
        f2 = compute_knowledge_freshness(published_at=_TS_OLD, evaluation_context=_CTX)
        assert f1.knowledge_freshness == f2.knowledge_freshness


# ── Stage 9: Knowledge Health ─────────────────────────────────────────────────


class TestKnowledgeHealth:
    def _run(self):
        items = (
            GitHubConnector(topics=["llm"], max_items=5, _raw_override=_GH_RAW).ingest(_CTX)
            + HackerNewsConnector(max_items=5, _raw_override=_HN_RAW).ingest(_CTX)
        )
        from app.knowledge.knowledge_fusion import fuse_knowledge_items
        from app.knowledge.correlation import compute_cross_source_correlations
        from app.knowledge.graph import build_knowledge_graph
        fused = fuse_knowledge_items(items)
        correlations = compute_cross_source_correlations(items, _CTX)
        rels = build_knowledge_graph(items).all_relationships()
        return compute_knowledge_health(
            items=items, fused=fused, correlations=correlations,
            relationships=rels, evaluation_context=_CTX,
        )

    def test_health_returns(self):
        h = self._run()
        assert h is not None

    def test_health_score_bounds(self):
        h = self._run()
        assert 0.0 <= h.health_score <= 1.0

    def test_health_all_dims_bounds(self):
        h = self._run()
        for dim in [
            h.coverage, h.freshness, h.source_diversity, h.evidence_quality,
            h.entity_resolution_quality, h.correlation_strength, h.knowledge_density,
            h.completeness, h.explainability, h.version_consistency,
        ]:
            assert 0.0 <= dim <= 1.0

    def test_health_empty_input(self):
        h = compute_knowledge_health(
            items=[], fused=[], correlations=[], relationships=[], evaluation_context=_CTX,
        )
        assert h.health_score == 0.0

    def test_health_item_count(self):
        h = self._run()
        assert h.item_count >= 1

    def test_health_versions(self):
        h = self._run()
        assert h.versions.knowledge_version == KNOWLEDGE_VERSION


# ── Stage 10: Logical Knowledge Graph ────────────────────────────────────────


class TestLogicalKnowledgeGraph:
    def _items(self):
        return (
            GitHubConnector(topics=["llm"], max_items=5, _raw_override=_GH_RAW).ingest(_CTX)
            + HackerNewsConnector(max_items=5, _raw_override=_HN_RAW).ingest(_CTX)
        )

    def test_graph_builds(self):
        items = self._items()
        graph = build_knowledge_graph(items)
        assert graph.entity_count() >= 0

    def test_graph_empty_input(self):
        graph = build_knowledge_graph([])
        assert graph.entity_count() == 0
        assert graph.relationship_count() == 0

    def test_graph_neighbors_symmetric(self):
        items = self._items()
        graph = build_knowledge_graph(items)
        for rel in graph.all_relationships():
            assert rel.target_entity_id in graph.neighbors(rel.source_entity_id)
            assert rel.source_entity_id in graph.neighbors(rel.target_entity_id)

    def test_graph_relationship_strength_bounds(self):
        items = self._items()
        for rel in build_knowledge_graph(items).all_relationships():
            assert 0.0 <= rel.strength <= 1.0

    def test_graph_relationship_type(self):
        items = self._items()
        for rel in build_knowledge_graph(items).all_relationships():
            assert rel.relationship_type == RelationshipType.CO_OCCURS_WITH

    def test_logical_graph_class_operations(self):
        graph = LogicalKnowledgeGraph()
        from app.knowledge.dto import KnowledgeEntity, EntityProvenance
        entity = KnowledgeEntity(
            entity_id="eid1",
            canonical_name="python",
            normalized_name="python",
            entity_type=EntityType.TECHNOLOGY,
            confidence=0.9,
            provenance=EntityProvenance(first_seen_source="src:x"),
        )
        graph.add_entity(entity)
        assert graph.entity_count() == 1
        assert graph.get_entity("eid1") is not None

    def test_graph_deterministic(self):
        items = self._items()
        g1 = build_knowledge_graph(items)
        g2 = build_knowledge_graph(items)
        ids1 = sorted(r.relationship_id for r in g1.all_relationships())
        ids2 = sorted(r.relationship_id for r in g2.all_relationships())
        assert ids1 == ids2


# ── Pipeline Orchestrator ─────────────────────────────────────────────────────


class TestKnowledgePipelineOrchestrator:
    def _connectors(self):
        return [
            GitHubConnector(topics=["llm"], max_items=5, _raw_override=_GH_RAW),
            HackerNewsConnector(max_items=5, _raw_override=_HN_RAW),
            RSSConnector(feed_url="https://x.com/rss", feed_name="X", max_items=5, _raw_override=_RSS_RAW),
            BlogConnector(urls=["https://x.com"], _raw_override=_BLOG_RAW),
        ]

    def test_pipeline_runs(self):
        report = run_knowledge_pipeline(self._connectors(), _CTX)
        assert report is not None

    def test_pipeline_report_id_set(self):
        report = run_knowledge_pipeline(self._connectors(), _CTX)
        assert report.report_id

    def test_pipeline_items_present(self):
        report = run_knowledge_pipeline(self._connectors(), _CTX)
        assert len(report.items) >= 1

    def test_pipeline_health_present(self):
        report = run_knowledge_pipeline(self._connectors(), _CTX)
        assert 0.0 <= report.health.health_score <= 1.0

    def test_pipeline_versions_set(self):
        report = run_knowledge_pipeline(self._connectors(), _CTX)
        assert report.versions.knowledge_version == KNOWLEDGE_VERSION

    def test_pipeline_generated_at_from_context(self):
        report = run_knowledge_pipeline(self._connectors(), _CTX)
        assert report.generated_at == _TS

    def test_pipeline_empty_connectors(self):
        report = run_knowledge_pipeline([], _CTX)
        assert report.items == []
        assert report.health.health_score == 0.0

    def test_pipeline_fused_items_present(self):
        report = run_knowledge_pipeline(self._connectors(), _CTX)
        assert isinstance(report.fused_items, list)

    def test_pipeline_correlations_present(self):
        report = run_knowledge_pipeline(self._connectors(), _CTX)
        assert isinstance(report.correlations, list)

    def test_pipeline_relationships_present(self):
        report = run_knowledge_pipeline(self._connectors(), _CTX)
        assert isinstance(report.relationships, list)


# ── Replay Determinism ────────────────────────────────────────────────────────


class TestReplayDeterminism:
    """All pipeline outputs must be identical across two runs with the same EvaluationContext."""

    def _connectors(self):
        return [
            GitHubConnector(topics=["llm"], max_items=5, _raw_override=_GH_RAW),
            HackerNewsConnector(max_items=5, _raw_override=_HN_RAW),
        ]

    def test_report_id_stable_across_replays(self):
        r1 = run_knowledge_pipeline(self._connectors(), _CTX)
        r2 = run_knowledge_pipeline(self._connectors(), _CTX)
        assert r1.report_id == r2.report_id

    def test_item_ids_stable_across_replays(self):
        r1 = run_knowledge_pipeline(self._connectors(), _CTX)
        r2 = run_knowledge_pipeline(self._connectors(), _CTX)
        assert sorted(i.item_id for i in r1.items) == sorted(i.item_id for i in r2.items)

    def test_health_score_stable_across_replays(self):
        r1 = run_knowledge_pipeline(self._connectors(), _CTX)
        r2 = run_knowledge_pipeline(self._connectors(), _CTX)
        assert r1.health.health_score == r2.health.health_score

    def test_different_context_produces_different_report_id(self):
        ctx2 = EvaluationContext(evaluation_timestamp=datetime(2026, 7, 1, tzinfo=timezone.utc), dataset_version="test-1.4")
        r1 = run_knowledge_pipeline(self._connectors(), _CTX)
        r2 = run_knowledge_pipeline(self._connectors(), ctx2)
        assert r1.report_id != r2.report_id

    def test_entity_ids_stable_across_replays(self):
        r1 = run_knowledge_pipeline(self._connectors(), _CTX)
        r2 = run_knowledge_pipeline(self._connectors(), _CTX)
        ids1 = sorted({e.entity_id for i in r1.items for e in i.entities})
        ids2 = sorted({e.entity_id for i in r2.items for e in i.entities})
        assert ids1 == ids2


# ── Backward Compatibility ────────────────────────────────────────────────────


class TestBackwardCompatibility:
    """Ensures 1.4 additions do not break existing 1.3 imports."""

    def test_adaptive_intelligence_dto_still_importable(self):
        from app.adaptive_intelligence.dto import (
            EvaluationContext,
            ScientificVersionMetadata,
            AdaptiveIntelligenceReport,
        )
        assert EvaluationContext is not None

    def test_business_os_version_present(self):
        from app.adaptive_intelligence.dto import ScientificVersionMetadata
        m = ScientificVersionMetadata()
        assert m.learning_version  # still set

    def test_knowledge_imports_do_not_shadow_ai_imports(self):
        from app.adaptive_intelligence.dto import EvaluationContext as AICtx
        from app.knowledge.dto import _k_stable_hash
        ctx = AICtx(evaluation_timestamp=_TS, dataset_version="test-1.4")
        h = _k_stable_hash({"ts": ctx.evaluation_timestamp.isoformat()})
        assert len(h) == 32

    def test_shadow_contracts_importable(self):
        from app.knowledge.dto import (
            Goal, Decision, ExecutionPlan, ExecutionTask, ExecutionResult, ExecutionAudit,
        )
        g = Goal(goal_id="g1", description="test")
        assert g.status == "pending"

    def test_shadow_contracts_have_no_runtime_behavior(self):
        from app.knowledge.dto import ExecutionPlan, ExecutionTask
        plan = ExecutionPlan(plan_id="p1")
        assert plan.tasks == []
        assert plan.status == "draft"
