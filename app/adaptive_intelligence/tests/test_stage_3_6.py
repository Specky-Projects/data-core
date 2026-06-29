"""Stage 3.6 scientific readiness tests.

Covers:
- Deterministic replay (same inputs → same outputs)
- Version propagation across the pipeline
- Immutable feature provenance
- Confidence evolution tracking
- Longitudinal drift computation
- Learning saturation detection
- Scientific Learning Health scoring
- Freshness metrics (deterministic, wall-clock-free)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.adaptive_intelligence.dto import (
    ALGORITHM_VERSION,
    CALIBRATION_VERSION,
    EVIDENCE_VERSION,
    FEATURE_VERSION,
    LEARNING_VERSION,
    POLICY_VERSION,
    RESEARCH_VERSION,
    EvaluationContext,
    LearningSaturation,
    LongitudinalDriftMetric,
    ScientificVersionMetadata,
    build_confidence_evolution,
    build_decision_hash,
    build_feature_contributions,
    build_feature_provenance,
    build_scientific_lineage,
    compute_freshness,
    compute_learning_saturation,
    compute_longitudinal_drift,
    compute_scientific_health,
    derive_evaluation_context,
    filter_rows_for_context,
    stable_hash,
)
from app.adaptive_intelligence.strategy_feedback import StrategyFeedbackEngine
from app.adaptive_intelligence.orchestrator import AdaptiveIntelligenceOrchestrator

# ── Shared fixtures ────────────────────────────────────────────────────────────

_FIXED_TS = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
_FIXED_CONTEXT = EvaluationContext(
    evaluation_timestamp=_FIXED_TS,
    replay_mode=True,
    dataset_timestamp=_FIXED_TS,
    dataset_version="dataset:test-fixed-v1",
    replay_configuration={"derived_from": "test"},
    lookback_days=30,
)
_VERSIONS = ScientificVersionMetadata()


def _make_row(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    signal: str = "BUY",
    regime: str | None = "trending",
    price_change_pct: float = 1.5,
    max_adverse_pct: float = -0.5,
    max_favorable_pct: float = 2.0,
    outcome_correct: bool = True,
    signal_at: datetime | None = None,
    row_id: int = 1,
):
    obj = MagicMock()
    obj.id = row_id
    obj.symbol = symbol
    obj.timeframe = timeframe
    obj.signal = signal
    obj.regime = regime
    obj.price_change_pct = price_change_pct
    obj.max_adverse_pct = max_adverse_pct
    obj.max_favorable_pct = max_favorable_pct
    obj.outcome_correct = outcome_correct
    obj.signal_at = signal_at or (_FIXED_TS - timedelta(days=1))
    obj.outcome_at = obj.signal_at + timedelta(hours=4)
    obj.evaluated_at = obj.outcome_at
    return obj


def _engine_with_rows(rows: list, evaluation_context=None) -> StrategyFeedbackEngine:
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = rows
    return StrategyFeedbackEngine(
        db,
        lookback_days=30,
        evaluation_context=evaluation_context,
    )


# ── 1. Deterministic Replay ────────────────────────────────────────────────────

class TestDeterministicReplay:
    """Identical inputs with the same EvaluationContext must produce identical outputs."""

    def _rows(self):
        return [_make_row(row_id=i, price_change_pct=float(i % 3) - 0.5) for i in range(1, 16)]

    def test_same_context_same_hash(self):
        rows = self._rows()
        engine_a = _engine_with_rows(rows, _FIXED_CONTEXT)
        engine_b = _engine_with_rows(rows, _FIXED_CONTEXT)
        result_a = engine_a.evaluate()
        result_b = engine_b.evaluate()
        cl_a = result_a.continuous_learning
        cl_b = result_b.continuous_learning
        assert cl_a is not None and cl_b is not None
        assert cl_a.decision_hash == cl_b.decision_hash

    def test_same_context_same_recommendation(self):
        rows = self._rows()
        result_a = _engine_with_rows(rows, _FIXED_CONTEXT).evaluate()
        result_b = _engine_with_rows(rows, _FIXED_CONTEXT).evaluate()
        recs_a = [s.recommendation for s in result_a.slices]
        recs_b = [s.recommendation for s in result_b.slices]
        assert recs_a == recs_b

    def test_same_context_same_drift(self):
        rows = self._rows()
        result_a = _engine_with_rows(rows, _FIXED_CONTEXT).evaluate()
        result_b = _engine_with_rows(rows, _FIXED_CONTEXT).evaluate()
        drift_a = result_a.continuous_learning.longitudinal_drift
        drift_b = result_b.continuous_learning.longitudinal_drift
        assert [(d.window_days, d.confidence) for d in drift_a] == [
            (d.window_days, d.confidence) for d in drift_b
        ]

    def test_replay_mode_is_true_when_context_provided(self):
        result = _engine_with_rows(self._rows(), _FIXED_CONTEXT).evaluate()
        assert result.continuous_learning.evaluation_context.replay_mode is True

    def test_derive_context_is_deterministic(self):
        rows = self._rows()
        ctx_a = derive_evaluation_context(rows, 30)
        ctx_b = derive_evaluation_context(rows, 30)
        assert ctx_a.dataset_version == ctx_b.dataset_version
        assert ctx_a.evaluation_timestamp == ctx_b.evaluation_timestamp

    def test_derive_context_uses_max_row_timestamp(self):
        rows = self._rows()
        ctx = derive_evaluation_context(rows, 30)
        # _row_timestamp prefers outcome_at then evaluated_at then signal_at
        from app.adaptive_intelligence.dto import _row_timestamp
        max_ts = max(_row_timestamp(r) for r in rows if _row_timestamp(r) is not None)
        assert ctx.evaluation_timestamp == max_ts

    def test_filter_rows_is_deterministic(self):
        rows = self._rows()
        filtered_a = filter_rows_for_context(rows, _FIXED_CONTEXT, 30)
        filtered_b = filter_rows_for_context(rows, _FIXED_CONTEXT, 30)
        assert len(filtered_a) == len(filtered_b)

    def test_orchestrator_with_fixed_context_is_deterministic(self):
        rows = self._rows()
        for db_mock in [MagicMock(), MagicMock()]:
            db_mock.query.return_value.filter.return_value.all.return_value = rows
        db_a = MagicMock()
        db_a.query.return_value.filter.return_value.all.return_value = rows
        db_b = MagicMock()
        db_b.query.return_value.filter.return_value.all.return_value = rows
        report_a = AdaptiveIntelligenceOrchestrator(
            db_a, lookback_days=30, environment="test", evaluation_context=_FIXED_CONTEXT
        ).evaluate()
        report_b = AdaptiveIntelligenceOrchestrator(
            db_b, lookback_days=30, environment="test", evaluation_context=_FIXED_CONTEXT
        ).evaluate()
        assert report_a.decision_hash == report_b.decision_hash
        assert report_a.overall_recommendation == report_b.overall_recommendation


# ── 2. Scientific Version Metadata ─────────────────────────────────────────────

class TestScientificVersionMetadata:
    def test_all_version_constants_present(self):
        meta = ScientificVersionMetadata()
        assert meta.learning_version == LEARNING_VERSION
        assert meta.calibration_version == CALIBRATION_VERSION
        assert meta.feature_version == FEATURE_VERSION
        assert meta.policy_version == POLICY_VERSION
        assert meta.algorithm_version == ALGORITHM_VERSION
        assert meta.research_version == RESEARCH_VERSION
        assert meta.evidence_version == EVIDENCE_VERSION

    def test_no_empty_version_fields(self):
        meta = ScientificVersionMetadata()
        for field, value in meta.model_dump(mode="json").items():
            assert value, f"Version field '{field}' must not be empty"

    def test_versions_propagate_to_slice(self):
        rows = [_make_row(row_id=i) for i in range(1, 16)]
        result = _engine_with_rows(rows, _FIXED_CONTEXT).evaluate()
        for slice_ in result.slices:
            assert slice_.versions.learning_version == LEARNING_VERSION

    def test_versions_propagate_to_profile(self):
        rows = [_make_row(row_id=i) for i in range(1, 16)]
        result = _engine_with_rows(rows, _FIXED_CONTEXT).evaluate()
        profile = result.continuous_learning
        assert profile is not None
        assert profile.versions.learning_version == LEARNING_VERSION

    def test_versions_in_orchestrator_report(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        report = AdaptiveIntelligenceOrchestrator(
            db, lookback_days=30, environment="test"
        ).evaluate()
        assert report.versions.algorithm_version == ALGORITHM_VERSION


# ── 3. Immutable Feature Provenance ───────────────────────────────────────────

class TestFeatureProvenance:
    def test_provenance_has_all_fields(self):
        prov = build_feature_provenance(
            evaluation_context=_FIXED_CONTEXT,
            entity_id="test_entity",
            features={"win_rate": 0.6},
            evidence_ids=["e1", "e2"],
            versions=_VERSIONS,
        )
        assert prov.dataset_version == _FIXED_CONTEXT.dataset_version
        assert prov.feature_hash
        assert prov.evidence_hash
        assert prov.feature_snapshot_id
        assert prov.research_version == RESEARCH_VERSION
        assert prov.policy_version == POLICY_VERSION

    def test_same_inputs_same_provenance(self):
        kwargs = dict(
            evaluation_context=_FIXED_CONTEXT,
            entity_id="test_entity",
            features={"win_rate": 0.6},
            evidence_ids=["e1", "e2"],
            versions=_VERSIONS,
        )
        prov_a = build_feature_provenance(**kwargs)
        prov_b = build_feature_provenance(**kwargs)
        assert prov_a.feature_hash == prov_b.feature_hash
        assert prov_a.evidence_hash == prov_b.evidence_hash
        assert prov_a.feature_snapshot_id == prov_b.feature_snapshot_id

    def test_different_features_different_hash(self):
        base = dict(evaluation_context=_FIXED_CONTEXT, entity_id="e", evidence_ids=[], versions=_VERSIONS)
        prov_a = build_feature_provenance(features={"win_rate": 0.6}, **base)
        prov_b = build_feature_provenance(features={"win_rate": 0.7}, **base)
        assert prov_a.feature_hash != prov_b.feature_hash

    def test_different_evidence_different_hash(self):
        base = dict(evaluation_context=_FIXED_CONTEXT, entity_id="e", features={}, versions=_VERSIONS)
        prov_a = build_feature_provenance(evidence_ids=["e1"], **base)
        prov_b = build_feature_provenance(evidence_ids=["e2"], **base)
        assert prov_a.evidence_hash != prov_b.evidence_hash

    def test_provenance_on_each_slice(self):
        rows = [_make_row(row_id=i) for i in range(1, 16)]
        result = _engine_with_rows(rows, _FIXED_CONTEXT).evaluate()
        for slice_ in result.slices:
            assert slice_.provenance is not None
            assert slice_.provenance.feature_hash
            assert slice_.provenance.evidence_hash

    def test_decision_hash_is_reproducible(self):
        prov = build_feature_provenance(
            evaluation_context=_FIXED_CONTEXT,
            entity_id="x",
            features={"a": 1},
            evidence_ids=["e1"],
            versions=_VERSIONS,
        )
        h1 = build_decision_hash(
            evaluation_context=_FIXED_CONTEXT,
            versions=_VERSIONS,
            provenance=prov,
            entity_id="x",
            recommendation="KEEP",
        )
        h2 = build_decision_hash(
            evaluation_context=_FIXED_CONTEXT,
            versions=_VERSIONS,
            provenance=prov,
            entity_id="x",
            recommendation="KEEP",
        )
        assert h1 == h2

    def test_scientific_lineage_fields(self):
        lin = build_scientific_lineage(
            entity_id="test",
            evidence_hash="abc",
            feature_hash="def",
            decision_hash="ghi",
            recommendation="KEEP",
        )
        assert lin.outcome == "TradingSignalOutcome"
        assert lin.learning == LEARNING_VERSION
        assert lin.policy == POLICY_VERSION
        assert lin.recommendation == "test:KEEP"


# ── 4. Confidence Evolution ────────────────────────────────────────────────────

class TestConfidenceEvolution:
    def test_deltas_are_computed(self):
        cev = build_confidence_evolution(initial=0.4, calibrated=0.5, learned=0.6, final=0.65)
        assert cev.initial_to_calibrated_delta == pytest.approx(0.1, abs=1e-4)
        assert cev.calibrated_to_learned_delta == pytest.approx(0.1, abs=1e-4)
        assert cev.learned_to_final_delta == pytest.approx(0.05, abs=1e-4)
        assert cev.total_delta == pytest.approx(0.25, abs=1e-4)

    def test_zero_evolution(self):
        cev = build_confidence_evolution(initial=0.5, calibrated=0.5, learned=0.5, final=0.5)
        assert cev.total_delta == 0.0

    def test_negative_delta(self):
        cev = build_confidence_evolution(initial=0.8, calibrated=0.7, learned=0.6, final=0.55)
        assert cev.total_delta == pytest.approx(-0.25, abs=1e-4)

    def test_slices_have_confidence_evolution(self):
        rows = [_make_row(row_id=i) for i in range(1, 16)]
        result = _engine_with_rows(rows, _FIXED_CONTEXT).evaluate()
        for slice_ in result.slices:
            assert slice_.confidence_evolution is not None
            cev = slice_.confidence_evolution
            assert 0.0 <= cev.initial_confidence <= 1.0
            assert 0.0 <= cev.final_confidence <= 1.0

    def test_feature_contributions_ranked(self):
        contributions = build_feature_contributions(
            {"accuracy": 0.45, "economic": 0.35, "coverage": 0.20}
        )
        assert contributions[0].rank == 1
        assert contributions[0].feature == "accuracy"
        assert all(c.normalized_contribution >= 0.0 for c in contributions)
        total = sum(c.normalized_contribution for c in contributions)
        assert total == pytest.approx(1.0, abs=1e-4)


# ── 5. Longitudinal Drift ─────────────────────────────────────────────────────

class TestLongitudinalDrift:
    def _many_rows(self, n: int = 50) -> list:
        return [
            _make_row(
                row_id=i,
                price_change_pct=1.0 if i % 2 == 0 else -0.5,
                outcome_correct=(i % 2 == 0),
                signal_at=_FIXED_TS - timedelta(days=i % 365),
            )
            for i in range(1, n + 1)
        ]

    def test_drift_returns_five_windows(self):
        rows = self._many_rows(50)
        drift = compute_longitudinal_drift(rows, _FIXED_CONTEXT)
        assert [d.window_days for d in drift] == [7, 30, 90, 180, 365]

    def test_drift_all_fields_present(self):
        rows = self._many_rows(50)
        for metric in compute_longitudinal_drift(rows, _FIXED_CONTEXT):
            assert 0.0 <= metric.confidence <= 1.0
            assert 0.0 <= metric.stability <= 1.0
            assert 0.0 <= metric.volatility <= 1.0
            assert 0.0 <= metric.degradation <= 0.5
            assert 0.0 <= metric.improvement <= 0.5
            assert metric.sample_size >= 0

    def test_drift_is_deterministic(self):
        rows = self._many_rows(50)
        drift_a = compute_longitudinal_drift(rows, _FIXED_CONTEXT)
        drift_b = compute_longitudinal_drift(rows, _FIXED_CONTEXT)
        for a, b in zip(drift_a, drift_b):
            assert a.confidence == b.confidence
            assert a.stability == b.stability

    def test_empty_rows_returns_zeros(self):
        drift = compute_longitudinal_drift([], _FIXED_CONTEXT)
        for metric in drift:
            assert metric.sample_size == 0
            assert metric.confidence == 0.0

    def test_slices_carry_drift_in_profile(self):
        rows = self._many_rows(30)
        result = _engine_with_rows(rows, _FIXED_CONTEXT).evaluate()
        profile = result.continuous_learning
        assert len(profile.longitudinal_drift) == 5


# ── 6. Learning Saturation ────────────────────────────────────────────────────

class TestLearningSaturation:
    def test_saturation_from_stable_drift(self):
        drift = [
            LongitudinalDriftMetric(window_days=7, sample_size=10, confidence=0.62, stability=0.8, volatility=0.2, degradation=0.0, improvement=0.12),
            LongitudinalDriftMetric(window_days=30, sample_size=30, confidence=0.61, stability=0.8, volatility=0.2, degradation=0.0, improvement=0.11),
        ]
        sat = compute_learning_saturation(drift)
        assert sat.plateau_detected is True  # marginal gain < 0.02
        assert 0.0 <= sat.saturation_score <= 1.0

    def test_saturation_from_diverging_drift(self):
        drift = [
            LongitudinalDriftMetric(window_days=7, sample_size=10, confidence=0.70, stability=0.7, volatility=0.3, degradation=0.0, improvement=0.20),
            LongitudinalDriftMetric(window_days=365, sample_size=200, confidence=0.50, stability=0.5, volatility=0.5, degradation=0.0, improvement=0.0),
        ]
        sat = compute_learning_saturation(drift)
        assert sat.marginal_gain == pytest.approx(0.20, abs=1e-4)
        assert sat.plateau_detected is False

    def test_saturation_with_single_window(self):
        drift = [
            LongitudinalDriftMetric(window_days=7, sample_size=5, confidence=0.6, stability=0.8, volatility=0.2, degradation=0.0, improvement=0.1),
        ]
        sat = compute_learning_saturation(drift)
        assert sat.saturation_score == 0.0
        assert sat.plateau_detected is False

    def test_profile_has_saturation(self):
        rows = [_make_row(row_id=i) for i in range(1, 16)]
        result = _engine_with_rows(rows, _FIXED_CONTEXT).evaluate()
        sat = result.continuous_learning.learning_saturation
        assert sat is not None
        assert 0.0 <= sat.saturation_score <= 1.0


# ── 7. Learning Health ────────────────────────────────────────────────────────

class TestScientificLearningHealth:
    def _baseline_health(self, **kwargs):
        defaults = dict(
            evaluation_context=_FIXED_CONTEXT,
            versions=_VERSIONS,
            evidence_ids=["e1", "e2", "e3", "e4", "e5", "e6", "e7", "e8", "e9", "e10"],
            drift=[
                LongitudinalDriftMetric(window_days=7, sample_size=10, confidence=0.6, stability=0.8, volatility=0.2, degradation=0.0, improvement=0.1),
                LongitudinalDriftMetric(window_days=30, sample_size=30, confidence=0.55, stability=0.75, volatility=0.25, degradation=0.0, improvement=0.05),
            ],
            saturation=LearningSaturation(saturation_score=0.9, marginal_gain=0.01, learning_velocity=0.0001, plateau_detected=True),
            explainability_present=True,
            calibration_quality=0.7,
            confidence_consistency=0.8,
        )
        defaults.update(kwargs)
        return compute_scientific_health(**defaults)

    def test_health_score_in_range(self):
        health = self._baseline_health()
        assert 0.0 <= health.health_score <= 1.0

    def test_replay_mode_raises_score(self):
        health_replay = self._baseline_health(evaluation_context=_FIXED_CONTEXT)
        no_replay_ctx = _FIXED_CONTEXT.model_copy(update={"replay_mode": False})
        health_no_replay = self._baseline_health(evaluation_context=no_replay_ctx)
        assert health_replay.replay_readiness > health_no_replay.replay_readiness

    def test_all_dimensions_present(self):
        health = self._baseline_health()
        for field in (
            "replay_readiness", "version_completeness", "evidence_quality",
            "feature_provenance", "learning_stability", "calibration_quality",
            "drift_stability", "learning_saturation", "explainability",
            "audit_completeness", "confidence_consistency",
        ):
            val = getattr(health, field)
            assert 0.0 <= val <= 1.0, f"{field}={val} out of range"

    def test_empty_evidence_lowers_quality(self):
        health = self._baseline_health(evidence_ids=[])
        assert health.evidence_quality == 0.0

    def test_profile_carries_scientific_health(self):
        rows = [_make_row(row_id=i) for i in range(1, 31)]
        result = _engine_with_rows(rows, _FIXED_CONTEXT).evaluate()
        health = result.continuous_learning.scientific_health
        assert health is not None
        assert 0.0 <= health.health_score <= 1.0

    def test_version_completeness_is_1_for_full_meta(self):
        health = self._baseline_health()
        assert health.version_completeness == 1.0


# ── 8. Freshness Metrics ──────────────────────────────────────────────────────

class TestFreshnessMetrics:
    def test_freshness_keys_present(self):
        rows = [_make_row(row_id=1, signal_at=_FIXED_TS - timedelta(days=1))]
        freshness = compute_freshness(rows, _FIXED_CONTEXT)
        assert set(freshness.keys()) == {
            "dataset_freshness", "evidence_freshness", "feature_freshness", "learning_freshness"
        }

    def test_fresh_data_high_scores(self):
        rows = [_make_row(row_id=i, signal_at=_FIXED_TS - timedelta(hours=i)) for i in range(1, 6)]
        freshness = compute_freshness(rows, _FIXED_CONTEXT)
        assert freshness["dataset_freshness"] > 0.9
        assert freshness["evidence_freshness"] > 0.8

    def test_stale_data_low_evidence_freshness(self):
        rows = [_make_row(row_id=1, signal_at=_FIXED_TS - timedelta(days=20))]
        freshness = compute_freshness(rows, _FIXED_CONTEXT)
        assert freshness["evidence_freshness"] < 0.1

    def test_empty_rows_all_zero(self):
        freshness = compute_freshness([], _FIXED_CONTEXT)
        assert all(v == 0.0 for v in freshness.values())

    def test_freshness_is_deterministic(self):
        rows = [_make_row(row_id=i, signal_at=_FIXED_TS - timedelta(days=i)) for i in range(1, 6)]
        f1 = compute_freshness(rows, _FIXED_CONTEXT)
        f2 = compute_freshness(rows, _FIXED_CONTEXT)
        assert f1 == f2

    def test_freshness_in_profile(self):
        rows = [_make_row(row_id=i, signal_at=_FIXED_TS - timedelta(days=i)) for i in range(1, 11)]
        result = _engine_with_rows(rows, _FIXED_CONTEXT).evaluate()
        freshness = result.continuous_learning.freshness
        assert "dataset_freshness" in freshness
        assert "evidence_freshness" in freshness
        assert "feature_freshness" in freshness
        assert "learning_freshness" in freshness

    def test_freshness_values_in_range(self):
        rows = [_make_row(row_id=i, signal_at=_FIXED_TS - timedelta(days=i)) for i in range(1, 11)]
        result = _engine_with_rows(rows, _FIXED_CONTEXT).evaluate()
        for key, value in result.continuous_learning.freshness.items():
            assert 0.0 <= value <= 1.0, f"{key}={value} out of range"

    def test_freshness_no_wall_clock_dependency(self):
        """Freshness must not call datetime.now() — proven by using fixed timestamps."""
        rows = [_make_row(row_id=1, signal_at=_FIXED_TS - timedelta(days=5))]
        f = compute_freshness(rows, _FIXED_CONTEXT)
        # dataset_freshness for 5 days out of 30-day window = 1 - 5/30 ≈ 0.833
        assert f["dataset_freshness"] == pytest.approx(1.0 - 5.0 / 30.0, abs=0.01)
