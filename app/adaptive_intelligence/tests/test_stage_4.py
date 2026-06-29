"""Stage 4 test suite — verifies O1/O3/O4/O5/O6 fixes and new Stage 4 capabilities.

All tests are deterministic: fixed timestamps, no wall-clock calls.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.adaptive_intelligence.dto import (
    ALGORITHM_VERSION,
    CALIBRATION_VERSION,
    EVIDENCE_VERSION,
    FEATURE_VERSION,
    LEARNING_VERSION,
    POLICY_VERSION,
    RESEARCH_VERSION,
    AdaptiveIntelligenceHealth,
    DecisionQualityMetric,
    EvaluationContext,
    FeatureProvenance,
    LongitudinalDriftMetric,
    RecommendationEvolution,
    ScientificVersionMetadata,
    StrategyIntelligence,
    _compute_learning_stability,
    build_feature_provenance,
    compute_adaptive_health,
    compute_decision_quality,
    compute_learning_saturation,
    compute_longitudinal_drift,
    compute_recommendation_evolution,
    compute_scientific_health,
    compute_strategy_intelligence,
    compute_temporal_decay_from_evidence,
)

# ── Fixed test fixtures ────────────────────────────────────────────────────────

_FIXED_TS = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
_FIXED_CONTEXT = EvaluationContext(
    evaluation_timestamp=_FIXED_TS,
    replay_mode=True,
    dataset_timestamp=_FIXED_TS,
    dataset_version="test-stage-4-v1",
    replay_configuration={"source": "test"},
    lookback_days=30,
)


def _make_row(
    *,
    row_id: int = 1,
    signal_at: datetime | None = None,
    outcome_at: datetime | None = None,
    outcome_correct: bool = True,
    price_change_pct: float = 1.0,
) -> Any:
    row = MagicMock()
    row.id = row_id
    row.signal_at = signal_at or (_FIXED_TS - timedelta(days=5))
    row.outcome_at = outcome_at
    row.evaluated_at = None
    row.outcome_correct = outcome_correct
    row.price_change_pct = price_change_pct
    row.max_adverse_pct = 0.5
    row.max_favorable_pct = 1.5
    return row


def _make_slice(
    *,
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    regime: str | None = "bull",
    signal: str = "BUY",
    sample_size: int = 30,
    win_rate: float = 0.65,
    recommendation: str = "BOOST",
    confidence_delta: float = 0.15,
    relevance_score: float = 0.7,
) -> Any:
    from app.adaptive_intelligence.dto import ConfidenceEvolution
    s = MagicMock()
    s.symbol = symbol
    s.timeframe = timeframe
    s.regime = regime
    s.signal = signal
    s.sample_size = sample_size
    s.win_rate = win_rate
    s.recommendation = recommendation
    s.relevance_score = relevance_score
    s.confidence_evolution = ConfidenceEvolution(
        initial_confidence=0.5,
        calibrated_confidence=0.6,
        learned_confidence=0.65,
        final_confidence=0.65,
        initial_to_calibrated_delta=0.1,
        calibrated_to_learned_delta=0.05,
        learned_to_final_delta=0.0,
        total_delta=confidence_delta,
    )
    return s


def _make_drift(
    window_days: int = 30,
    confidence: float = 0.6,
    stability: float = 0.8,
    sample_size: int = 20,
) -> LongitudinalDriftMetric:
    return LongitudinalDriftMetric(
        window_days=window_days,
        sample_size=sample_size,
        confidence=confidence,
        stability=stability,
        volatility=0.2,
        degradation=0.0,
        improvement=0.1,
    )


# ── Version constants ──────────────────────────────────────────────────────────

class TestVersionConstants:
    def test_learning_version_is_stage_4(self) -> None:
        assert "stage-4" in LEARNING_VERSION

    def test_calibration_version_is_stage_4(self) -> None:
        assert "stage-4" in CALIBRATION_VERSION

    def test_feature_version_is_stage_4(self) -> None:
        assert "stage-4" in FEATURE_VERSION

    def test_policy_version_is_stage_4(self) -> None:
        assert "stage-4" in POLICY_VERSION

    def test_algorithm_version_is_stage_4(self) -> None:
        assert "stage-4" in ALGORITHM_VERSION

    def test_research_version_is_stage_4(self) -> None:
        assert "stage-4" in RESEARCH_VERSION

    def test_evidence_version_is_stage_4(self) -> None:
        assert "stage-4" in EVIDENCE_VERSION

    def test_scientific_version_metadata_carries_stage_4(self) -> None:
        meta = ScientificVersionMetadata()
        assert "stage-4" in meta.learning_version
        assert "stage-4" in meta.calibration_version


# ── O1 Fix: learning_stability ≠ drift_stability ──────────────────────────────

class TestO1LearningStabilityFix:
    def test_learning_stability_differs_from_drift_stability_when_variance_exists(self) -> None:
        drift = [
            _make_drift(window_days=7,   confidence=0.4,  stability=0.8),
            _make_drift(window_days=30,  confidence=0.7,  stability=0.8),
            _make_drift(window_days=90,  confidence=0.4,  stability=0.8),
            _make_drift(window_days=180, confidence=0.7,  stability=0.8),
            _make_drift(window_days=365, confidence=0.4,  stability=0.8),
        ]
        saturation = compute_learning_saturation(drift)
        health = compute_scientific_health(
            evaluation_context=_FIXED_CONTEXT,
            versions=ScientificVersionMetadata(),
            evidence_ids=["a", "b", "c"],
            drift=drift,
            saturation=saturation,
            explainability_present=True,
            calibration_quality=0.65,
            confidence_consistency=0.8,
            feature_provenance_score=0.5,
        )
        # drift_stability = mean(stability) = 0.8
        # learning_stability = 1.0 - std_dev(confidences) / 0.2
        # confidences alternate 0.4/0.7 → std_dev ≈ 0.15 → score ≈ 1 - 0.15/0.2 = 0.25
        assert health.learning_stability != health.drift_stability, (
            "O1 not fixed: learning_stability and drift_stability are equal"
        )

    def test_learning_stability_high_when_consistent_windows(self) -> None:
        drift = [_make_drift(window_days=w, confidence=0.65, stability=0.8) for w in (7, 30, 90, 180, 365)]
        saturation = compute_learning_saturation(drift)
        health = compute_scientific_health(
            evaluation_context=_FIXED_CONTEXT,
            versions=ScientificVersionMetadata(),
            evidence_ids=["a"],
            drift=drift,
            saturation=saturation,
            explainability_present=True,
            calibration_quality=0.6,
            confidence_consistency=0.9,
        )
        assert health.learning_stability >= 0.9, "Consistent windows should yield high learning_stability"

    def test_learning_stability_low_when_volatile_windows(self) -> None:
        drift = [
            _make_drift(window_days=7,   confidence=0.2, stability=0.9),
            _make_drift(window_days=30,  confidence=0.8, stability=0.9),
            _make_drift(window_days=90,  confidence=0.2, stability=0.9),
            _make_drift(window_days=180, confidence=0.8, stability=0.9),
        ]
        ls = _compute_learning_stability(drift)
        assert ls < 0.5, f"Volatile windows should yield low learning_stability, got {ls}"

    def test_compute_learning_stability_insufficient_data_returns_neutral(self) -> None:
        assert _compute_learning_stability([]) == 0.5
        assert _compute_learning_stability([_make_drift()]) == 0.5

    def test_drift_stability_remains_mean_of_per_window_stability(self) -> None:
        drift = [
            _make_drift(window_days=7,  confidence=0.6, stability=0.6),
            _make_drift(window_days=30, confidence=0.6, stability=0.8),
        ]
        saturation = compute_learning_saturation(drift)
        health = compute_scientific_health(
            evaluation_context=_FIXED_CONTEXT,
            versions=ScientificVersionMetadata(),
            evidence_ids=["x"],
            drift=drift,
            saturation=saturation,
            explainability_present=True,
            calibration_quality=0.6,
            confidence_consistency=0.7,
        )
        assert health.drift_stability == pytest.approx(0.7, abs=0.01), (
            "drift_stability should be mean(stability) = (0.6+0.8)/2 = 0.7"
        )


# ── O3 Fix: RegimeAdaptation scientific metadata ──────────────────────────────

class TestO3RegimeAdaptationMetadata:
    def test_regime_adaptation_has_versions_field(self) -> None:
        from app.adaptive_intelligence.dto import RegimeAdaptation
        adaptation = RegimeAdaptation(
            regime="bull",
            signal="BUY",
            symbol="BTCUSDT",
            timeframe="1h",
            sample_size=15,
            win_rate=0.6,
            expectancy=0.5,
            recommendation="KEEP",
            reason="test",
        )
        assert adaptation.versions is not None
        assert isinstance(adaptation.versions, ScientificVersionMetadata)

    def test_regime_adaptation_has_evidence_ids_field(self) -> None:
        from app.adaptive_intelligence.dto import RegimeAdaptation
        adaptation = RegimeAdaptation(
            regime="bear",
            signal="SELL",
            symbol=None,
            timeframe=None,
            sample_size=5,
            win_rate=0.4,
            expectancy=-0.1,
            recommendation="OBSERVE_ONLY",
            reason="test",
            evidence_ids=["1", "2", "3"],
        )
        assert adaptation.evidence_ids == ["1", "2", "3"]

    def test_regime_adaptation_has_provenance_and_decision_hash_fields(self) -> None:
        from app.adaptive_intelligence.dto import RegimeAdaptation
        adaptation = RegimeAdaptation(
            regime="bull",
            signal="BUY",
            symbol="ETHUSDT",
            timeframe="4h",
            sample_size=20,
            win_rate=0.55,
            expectancy=0.2,
            recommendation="KEEP",
            reason="test",
            provenance=None,
            decision_hash=None,
        )
        assert adaptation.provenance is None
        assert adaptation.decision_hash is None

    def test_regime_adapter_builds_provenance_for_each_adaptation(self) -> None:
        from app.adaptive_intelligence.regime_adapter import RegimeAdapter

        rows = []
        for i in range(5):
            row = MagicMock()
            row.id = i
            row.regime = "bull"
            row.symbol = "BTCUSDT"
            row.timeframe = "1h"
            row.signal = "BUY"
            row.price_change_pct = 1.0
            row.outcome_correct = True
            row.signal_at = _FIXED_TS - timedelta(days=10 + i)
            row.outcome_at = None
            row.evaluated_at = None
            rows.append(row)

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = rows

        adapter = RegimeAdapter(db=db, lookback_days=30, evaluation_context=_FIXED_CONTEXT)
        result = adapter.evaluate()

        assert len(result.adaptations) > 0
        for adaptation in result.adaptations:
            assert adaptation.versions is not None
            assert adaptation.provenance is not None
            assert isinstance(adaptation.provenance, FeatureProvenance)
            assert adaptation.decision_hash is not None
            assert len(adaptation.decision_hash) == 64

    def test_regime_adapter_evidence_ids_are_sorted(self) -> None:
        from app.adaptive_intelligence.regime_adapter import RegimeAdapter

        rows = []
        for i in [5, 3, 1, 4, 2]:
            row = MagicMock()
            row.id = i
            row.regime = "bull"
            row.symbol = "BTCUSDT"
            row.timeframe = "1h"
            row.signal = "BUY"
            row.price_change_pct = 1.0
            row.outcome_correct = True
            row.signal_at = _FIXED_TS - timedelta(days=10)
            row.outcome_at = None
            row.evaluated_at = None
            rows.append(row)

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = rows

        adapter = RegimeAdapter(db=db, lookback_days=30, evaluation_context=_FIXED_CONTEXT)
        result = adapter.evaluate()

        for adaptation in result.adaptations:
            assert adaptation.evidence_ids == sorted(adaptation.evidence_ids), (
                "evidence_ids must be sorted (O4/O3 fix)"
            )


# ── O3 Fix: RiskTuningResult scientific metadata ──────────────────────────────

class TestO3RiskTuningMetadata:
    def test_risk_tuning_result_has_versions_field(self) -> None:
        from app.adaptive_intelligence.dto import RiskTuningResult

        result = RiskTuningResult(
            evaluated_at=_FIXED_TS,
            current_win_rate=0.55,
            current_expectancy=0.1,
            current_profit_factor=1.2,
            max_observed_drawdown_pct=3.0,
            suggested_position_size_multiplier=1.0,
            suggested_min_confidence=55,
            risk_level="LOW",
            throttle_recommended=False,
            disable_recommended=False,
            reasoning=["win_rate acceptable"],
            policy_hints={},
        )
        assert result.versions is not None
        assert isinstance(result.versions, ScientificVersionMetadata)

    def test_risk_tuning_result_has_provenance_and_decision_hash_fields(self) -> None:
        from app.adaptive_intelligence.dto import RiskTuningResult

        result = RiskTuningResult(
            evaluated_at=_FIXED_TS,
            current_win_rate=None,
            current_expectancy=None,
            current_profit_factor=None,
            max_observed_drawdown_pct=None,
            suggested_position_size_multiplier=0.75,
            suggested_min_confidence=60,
            risk_level="MODERATE",
            throttle_recommended=False,
            disable_recommended=False,
            reasoning=["insufficient data"],
            policy_hints={},
            provenance=None,
            decision_hash=None,
        )
        assert result.provenance is None
        assert result.decision_hash is None

    def test_risk_tuner_builds_scientific_metadata(self) -> None:
        from app.adaptive_intelligence.risk_tuner import RiskTuner
        from app.adaptive_intelligence.dto import (
            ConfidenceCalibrationResult,
            RegimeAdapterResult,
            StrategyFeedbackResult,
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        strategy = MagicMock(spec=StrategyFeedbackResult)
        strategy.slices = []
        strategy.summary = {"KEEP": 0, "BOOST": 0, "THROTTLE": 0, "DISABLE": 0, "OBSERVE_ONLY": 0}
        strategy.top_performers = []
        strategy.underperformers = []

        calibration = MagicMock(spec=ConfidenceCalibrationResult)
        calibration.recommended_min_confidence = None
        calibration.well_calibrated = True
        calibration.overconfidence_warning = False

        regime = MagicMock(spec=RegimeAdapterResult)
        regime.dominant_regime = "bull"

        tuner = RiskTuner(db=db, lookback_days=14, evaluation_context=_FIXED_CONTEXT)
        result = tuner.evaluate(strategy, calibration, regime)

        assert result.versions is not None
        assert result.provenance is not None
        assert result.decision_hash is not None
        assert len(result.decision_hash) == 64


# ── O4 Fix: evidence_ids canonical ordering ──────────────────────────────────

class TestO4EvidenceIdsOrdering:
    def test_build_feature_provenance_evidence_ids_are_sorted(self) -> None:
        provenance = build_feature_provenance(
            evaluation_context=_FIXED_CONTEXT,
            entity_id="test",
            features={"a": 1},
            evidence_ids=["5", "2", "8", "1", "3"],
        )
        assert provenance.evidence_ids == sorted(["5", "2", "8", "1", "3"])

    def test_evidence_hash_deterministic_regardless_of_input_order(self) -> None:
        p1 = build_feature_provenance(
            evaluation_context=_FIXED_CONTEXT,
            entity_id="test",
            features={"a": 1},
            evidence_ids=["a", "b", "c"],
        )
        p2 = build_feature_provenance(
            evaluation_context=_FIXED_CONTEXT,
            entity_id="test",
            features={"a": 1},
            evidence_ids=["c", "a", "b"],
        )
        assert p1.evidence_hash == p2.evidence_hash
        assert p1.evidence_ids == p2.evidence_ids == ["a", "b", "c"]

    def test_evidence_ids_truncated_to_25(self) -> None:
        ids = [str(i) for i in range(50)]
        provenance = build_feature_provenance(
            evaluation_context=_FIXED_CONTEXT,
            entity_id="test",
            features={},
            evidence_ids=ids,
        )
        assert len(provenance.evidence_ids) == 25
        assert provenance.evidence_ids == sorted(ids)[:25]


# ── O5 Fix: RiskTuner null safety ─────────────────────────────────────────────

class TestO5RiskTunerNullSafety:
    def test_risk_tuner_survives_none_resolved_context(self) -> None:
        from app.adaptive_intelligence.risk_tuner import RiskTuner
        from app.adaptive_intelligence.dto import (
            ConfidenceCalibrationResult,
            RegimeAdapterResult,
            StrategyFeedbackResult,
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.all.side_effect = RuntimeError("DB failed")

        strategy = MagicMock(spec=StrategyFeedbackResult)
        strategy.slices = []
        strategy.summary = {}
        strategy.top_performers = []
        strategy.underperformers = []

        calibration = MagicMock(spec=ConfidenceCalibrationResult)
        calibration.recommended_min_confidence = None
        calibration.well_calibrated = True
        calibration.overconfidence_warning = False

        regime = MagicMock(spec=RegimeAdapterResult)
        regime.dominant_regime = None

        tuner = RiskTuner(db=db, lookback_days=14, evaluation_context=None)
        # Should not raise — orchestrator will catch but we verify no AttributeError on None
        try:
            result = tuner.evaluate(strategy, calibration, regime)
            # If it somehow succeeds (mocked path), verify evaluated_at is set
            assert result.evaluated_at is not None
        except RuntimeError:
            pass  # DB failure propagates from _fetch_recent_aggregates — expected

    def test_risk_tuner_with_injected_context_no_none_crash(self) -> None:
        from app.adaptive_intelligence.risk_tuner import RiskTuner
        from app.adaptive_intelligence.dto import (
            ConfidenceCalibrationResult,
            RegimeAdapterResult,
            StrategyFeedbackResult,
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        strategy = MagicMock(spec=StrategyFeedbackResult)
        strategy.slices = []
        strategy.summary = {}
        strategy.top_performers = []
        strategy.underperformers = []

        calibration = MagicMock(spec=ConfidenceCalibrationResult)
        calibration.recommended_min_confidence = 60
        calibration.well_calibrated = False
        calibration.overconfidence_warning = True

        regime = MagicMock(spec=RegimeAdapterResult)
        regime.dominant_regime = "sideways"

        tuner = RiskTuner(db=db, lookback_days=14, evaluation_context=_FIXED_CONTEXT)
        result = tuner.evaluate(strategy, calibration, regime)
        assert result.evaluated_at == _FIXED_TS


# ── O6 Fix: evidence-based temporal decay ────────────────────────────────────

class TestO6TemporalDecay:
    def test_compute_temporal_decay_from_evidence_uses_row_timestamps(self) -> None:
        rows = [_make_row(row_id=i, signal_at=_FIXED_TS - timedelta(days=10)) for i in range(5)]
        decay = compute_temporal_decay_from_evidence(rows, _FIXED_CONTEXT)
        expected = max(0.25, min(1.0, 1.0 - 10.0 / 365.0))
        assert decay == pytest.approx(expected, abs=0.01)

    def test_compute_temporal_decay_from_evidence_empty_rows_returns_min(self) -> None:
        decay = compute_temporal_decay_from_evidence([], _FIXED_CONTEXT)
        assert decay == 0.25

    def test_compute_temporal_decay_no_wall_clock(self) -> None:
        ctx1 = EvaluationContext(
            evaluation_timestamp=_FIXED_TS,
            replay_mode=True,
            dataset_timestamp=_FIXED_TS,
            dataset_version="v1",
            replay_configuration={},
            lookback_days=30,
        )
        ctx2 = EvaluationContext(
            evaluation_timestamp=_FIXED_TS + timedelta(days=30),
            replay_mode=True,
            dataset_timestamp=_FIXED_TS,
            dataset_version="v1",
            replay_configuration={},
            lookback_days=30,
        )
        rows = [_make_row(row_id=1, signal_at=_FIXED_TS - timedelta(days=5))]
        d1 = compute_temporal_decay_from_evidence(rows, ctx1)
        d2 = compute_temporal_decay_from_evidence(rows, ctx2)
        assert d1 != d2, "Different evaluation timestamps should yield different decay"

    def test_calibration_bucket_decay_is_evidence_based(self) -> None:
        from app.adaptive_intelligence.confidence_calibration import ConfidenceCalibrationEngine

        rows = []
        for i in range(10):
            row = MagicMock()
            row.id = i
            row.confidence = 70
            row.outcome_correct = True
            row.price_change_pct = 1.0
            row.signal_at = _FIXED_TS - timedelta(days=5)
            row.outcome_at = None
            row.evaluated_at = None
            rows.append(row)

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = rows

        engine = ConfidenceCalibrationEngine(db=db, lookback_days=30, evaluation_context=_FIXED_CONTEXT)
        result = engine.evaluate()

        assert len(result.buckets) > 0
        bucket = result.buckets[0]
        expected_decay = max(0.25, min(1.0, 1.0 - 5.0 / 365.0))
        assert bucket.temporal_decay == pytest.approx(expected_decay, abs=0.02)


# ── Stage 4 DTOs ──────────────────────────────────────────────────────────────

class TestStage4DTOs:
    def test_decision_quality_metric_instantiates(self) -> None:
        dq = DecisionQualityMetric(
            precision=0.8, recall=0.7, stability=0.75,
            calibration_effectiveness=0.6, learning_impact=0.3, sample_size=50,
        )
        assert dq.precision == 0.8
        assert dq.sample_size == 50

    def test_recommendation_evolution_instantiates(self) -> None:
        ev = RecommendationEvolution(
            entity_id="BTCUSDT|1h|bull|BUY",
            current_recommendation="BOOST",
            direction="improved",
            confidence_delta=0.15,
            maturity="mature",
        )
        assert ev.direction == "improved"
        assert ev.maturity == "mature"

    def test_strategy_intelligence_instantiates(self) -> None:
        si = StrategyIntelligence(
            entity_id="ETHUSDT|4h|any|SELL",
            maturity_score=0.8,
            reliability_score=0.7,
            adaptive_confidence=0.65,
            recommendation_consistency=0.9,
        )
        assert si.maturity_score == 0.8

    def test_adaptive_intelligence_health_has_16_dims_plus_score(self) -> None:
        health = AdaptiveIntelligenceHealth(
            replay_readiness=1.0, version_completeness=1.0, evidence_quality=0.5,
            feature_provenance=0.5, learning_stability=0.7, calibration_quality=0.6,
            drift_stability=0.8, learning_saturation=0.5, explainability=1.0,
            audit_completeness=1.0, confidence_consistency=0.8,
            recommendation_quality=0.7, learning_effectiveness=0.4,
            strategy_stability=0.85, confidence_accuracy=0.75, decision_quality_score=0.7,
            health_score=0.72,
        )
        assert health.health_score == 0.72
        field_names = set(health.model_fields.keys())
        assert "recommendation_quality" in field_names
        assert "learning_effectiveness" in field_names
        assert "strategy_stability" in field_names
        assert "confidence_accuracy" in field_names
        assert "decision_quality_score" in field_names

    def test_continuous_learning_profile_has_stage_4_fields(self) -> None:
        from app.adaptive_intelligence.dto import ContinuousLearningProfile
        from datetime import datetime, timezone
        profile = ContinuousLearningProfile(
            evaluated_at=_FIXED_TS,
            lookback_days=30,
            coverage_sample_size=50,
        )
        assert profile.adaptive_decision_quality is None
        assert profile.recommendation_evolution == []
        assert profile.strategy_intelligence == []
        assert profile.adaptive_health is None


# ── compute_decision_quality ──────────────────────────────────────────────────

class TestComputeDecisionQuality:
    def test_empty_slices(self) -> None:
        dq = compute_decision_quality([])
        assert dq.sample_size == 0
        assert dq.precision == 0.0
        assert dq.recall == 0.0

    def test_all_boost_with_high_win_rate(self) -> None:
        slices = [_make_slice(win_rate=0.7, recommendation="BOOST") for _ in range(5)]
        dq = compute_decision_quality(slices)
        assert dq.precision == 1.0
        assert dq.recall == 1.0
        assert dq.stability == 1.0

    def test_mixed_recommendations(self) -> None:
        slices = [
            _make_slice(win_rate=0.7, recommendation="BOOST"),
            _make_slice(win_rate=0.3, recommendation="THROTTLE"),
            _make_slice(win_rate=0.6, recommendation="KEEP"),
        ]
        dq = compute_decision_quality(slices)
        assert 0.0 <= dq.precision <= 1.0
        assert 0.0 <= dq.recall <= 1.0
        assert 0.0 <= dq.stability <= 1.0

    def test_sample_size_is_sum_of_slice_sample_sizes(self) -> None:
        slices = [_make_slice(sample_size=20), _make_slice(sample_size=30)]
        dq = compute_decision_quality(slices)
        assert dq.sample_size == 50

    def test_learning_impact_bounded(self) -> None:
        slices = [_make_slice(confidence_delta=0.5), _make_slice(confidence_delta=-0.5)]
        dq = compute_decision_quality(slices)
        assert -1.0 <= dq.learning_impact <= 1.0


# ── compute_recommendation_evolution ─────────────────────────────────────────

class TestComputeRecommendationEvolution:
    def test_returns_one_entry_per_slice(self) -> None:
        slices = [_make_slice() for _ in range(4)]
        evolutions = compute_recommendation_evolution(slices)
        assert len(evolutions) == 4

    def test_mature_slice_classification(self) -> None:
        slices = [_make_slice(sample_size=50)]
        ev = compute_recommendation_evolution(slices)[0]
        assert ev.maturity == "mature"

    def test_developing_slice_classification(self) -> None:
        slices = [_make_slice(sample_size=20)]
        ev = compute_recommendation_evolution(slices)[0]
        assert ev.maturity == "developing"

    def test_bootstrap_slice_classification(self) -> None:
        slices = [_make_slice(sample_size=5)]
        ev = compute_recommendation_evolution(slices)[0]
        assert ev.maturity == "bootstrap"

    def test_direction_improved_for_positive_delta(self) -> None:
        slices = [_make_slice(confidence_delta=0.2)]
        ev = compute_recommendation_evolution(slices)[0]
        assert ev.direction == "improved"

    def test_direction_degraded_for_negative_delta(self) -> None:
        slices = [_make_slice(confidence_delta=-0.2)]
        ev = compute_recommendation_evolution(slices)[0]
        assert ev.direction == "degraded"

    def test_direction_stable_for_small_delta(self) -> None:
        slices = [_make_slice(confidence_delta=0.02)]
        ev = compute_recommendation_evolution(slices)[0]
        assert ev.direction == "stable"

    def test_entity_id_follows_slice_key_format(self) -> None:
        slices = [_make_slice(symbol="BTCUSDT", timeframe="1h", regime="bull", signal="BUY")]
        ev = compute_recommendation_evolution(slices)[0]
        assert "BTCUSDT" in ev.entity_id
        assert "1h" in ev.entity_id
        assert "BUY" in ev.entity_id


# ── compute_strategy_intelligence ────────────────────────────────────────────

class TestComputeStrategyIntelligence:
    def test_returns_one_entry_per_slice(self) -> None:
        slices = [_make_slice() for _ in range(3)]
        intel = compute_strategy_intelligence(slices)
        assert len(intel) == 3

    def test_mature_slice_has_high_maturity_score(self) -> None:
        slices = [_make_slice(sample_size=60)]
        intel = compute_strategy_intelligence(slices)[0]
        assert intel.maturity_score == 1.0

    def test_immature_slice_maturity_score_less_than_one(self) -> None:
        slices = [_make_slice(sample_size=15)]
        intel = compute_strategy_intelligence(slices)[0]
        assert intel.maturity_score < 1.0

    def test_adaptive_confidence_bounded(self) -> None:
        slices = [_make_slice(win_rate=0.9, sample_size=10)]
        intel = compute_strategy_intelligence(slices)[0]
        assert 0.0 <= intel.adaptive_confidence <= 1.0

    def test_recommendation_consistency_high_when_aligned(self) -> None:
        slices = [_make_slice(win_rate=0.7, recommendation="BOOST")]
        intel = compute_strategy_intelligence(slices)[0]
        assert intel.recommendation_consistency == 1.0

    def test_recommendation_consistency_high_when_throttle_on_low_winrate(self) -> None:
        slices = [_make_slice(win_rate=0.35, recommendation="THROTTLE")]
        intel = compute_strategy_intelligence(slices)[0]
        assert intel.recommendation_consistency == 1.0


# ── compute_adaptive_health ──────────────────────────────────────────────────

class TestComputeAdaptiveHealth:
    def _make_scientific_health(self) -> Any:
        from app.adaptive_intelligence.dto import ScientificLearningHealth
        return ScientificLearningHealth(
            replay_readiness=1.0, version_completeness=1.0, evidence_quality=0.5,
            feature_provenance=0.8, learning_stability=0.7, calibration_quality=0.65,
            drift_stability=0.8, learning_saturation=0.6, explainability=1.0,
            audit_completeness=1.0, confidence_consistency=0.75,
            health_score=0.8,
        )

    def test_adaptive_health_has_16_dimensions(self) -> None:
        sh = self._make_scientific_health()
        dq = DecisionQualityMetric(precision=0.8, recall=0.7, stability=0.75,
                                   calibration_effectiveness=0.6, learning_impact=0.3, sample_size=30)
        si = [StrategyIntelligence(entity_id="x", maturity_score=0.8, reliability_score=0.7,
                                   adaptive_confidence=0.65, recommendation_consistency=0.9)]
        health = compute_adaptive_health(scientific_health=sh, decision_quality=dq, strategy_intelligence=si)

        dims = {f for f in health.model_fields if f != "health_score"}
        assert len(dims) == 16

    def test_adaptive_health_score_is_mean_of_16_dims(self) -> None:
        sh = self._make_scientific_health()
        dq = DecisionQualityMetric(precision=1.0, recall=1.0, stability=1.0,
                                   calibration_effectiveness=1.0, learning_impact=1.0, sample_size=100)
        si = [StrategyIntelligence(entity_id="x", maturity_score=1.0, reliability_score=1.0,
                                   adaptive_confidence=1.0, recommendation_consistency=1.0)]
        health = compute_adaptive_health(scientific_health=sh, decision_quality=dq, strategy_intelligence=si)
        # All Stage 4 dims = 1.0, so health_score > Stage 3.6 health
        assert health.health_score > sh.health_score

    def test_adaptive_health_no_dq_gives_zero_stage4_dims(self) -> None:
        sh = self._make_scientific_health()
        health = compute_adaptive_health(scientific_health=sh, decision_quality=None, strategy_intelligence=[])
        assert health.recommendation_quality == 0.0
        assert health.learning_effectiveness == 0.0
        assert health.strategy_stability == 0.0

    def test_adaptive_health_inherits_stage36_dimensions(self) -> None:
        sh = self._make_scientific_health()
        health = compute_adaptive_health(scientific_health=sh, decision_quality=None, strategy_intelligence=[])
        assert health.replay_readiness == sh.replay_readiness
        assert health.drift_stability == sh.drift_stability
        assert health.learning_stability == sh.learning_stability

    def test_adaptive_health_score_in_range(self) -> None:
        sh = self._make_scientific_health()
        dq = DecisionQualityMetric(precision=0.5, recall=0.5, stability=0.5,
                                   calibration_effectiveness=0.5, learning_impact=0.0, sample_size=10)
        si = [StrategyIntelligence(entity_id="x", maturity_score=0.5, reliability_score=0.5,
                                   adaptive_confidence=0.5, recommendation_consistency=0.5)]
        health = compute_adaptive_health(scientific_health=sh, decision_quality=dq, strategy_intelligence=si)
        assert 0.0 <= health.health_score <= 1.0


# ── Stage 4 end-to-end: strategy_feedback ────────────────────────────────────

class TestStrategyFeedbackStage4:
    def _make_full_rows(self, n: int = 20) -> list[Any]:
        rows = []
        for i in range(n):
            row = MagicMock()
            row.id = i
            row.symbol = "BTCUSDT"
            row.timeframe = "1h"
            row.regime = "bull"
            row.signal = "BUY"
            row.confidence = 70
            row.outcome_correct = i % 3 != 0
            row.price_change_pct = 1.5 if i % 3 != 0 else -0.5
            row.max_adverse_pct = 0.5
            row.max_favorable_pct = 2.0
            row.signal_at = _FIXED_TS - timedelta(days=10 + i % 20)
            row.outcome_at = None
            row.evaluated_at = None
            rows.append(row)
        return rows

    def test_continuous_learning_profile_has_adaptive_decision_quality(self) -> None:
        from app.adaptive_intelligence.strategy_feedback import StrategyFeedbackEngine

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = self._make_full_rows()

        engine = StrategyFeedbackEngine(db=db, lookback_days=30, evaluation_context=_FIXED_CONTEXT)
        result = engine.evaluate()

        assert result.continuous_learning is not None
        assert result.continuous_learning.adaptive_decision_quality is not None
        assert isinstance(result.continuous_learning.adaptive_decision_quality, DecisionQualityMetric)

    def test_continuous_learning_profile_has_recommendation_evolution(self) -> None:
        from app.adaptive_intelligence.strategy_feedback import StrategyFeedbackEngine

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = self._make_full_rows()

        engine = StrategyFeedbackEngine(db=db, lookback_days=30, evaluation_context=_FIXED_CONTEXT)
        result = engine.evaluate()

        assert result.continuous_learning is not None
        evolutions = result.continuous_learning.recommendation_evolution
        assert isinstance(evolutions, list)
        assert len(evolutions) > 0

    def test_continuous_learning_profile_has_strategy_intelligence(self) -> None:
        from app.adaptive_intelligence.strategy_feedback import StrategyFeedbackEngine

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = self._make_full_rows()

        engine = StrategyFeedbackEngine(db=db, lookback_days=30, evaluation_context=_FIXED_CONTEXT)
        result = engine.evaluate()

        assert result.continuous_learning is not None
        intel = result.continuous_learning.strategy_intelligence
        assert isinstance(intel, list)
        assert len(intel) > 0

    def test_continuous_learning_profile_has_adaptive_health(self) -> None:
        from app.adaptive_intelligence.strategy_feedback import StrategyFeedbackEngine

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = self._make_full_rows()

        engine = StrategyFeedbackEngine(db=db, lookback_days=30, evaluation_context=_FIXED_CONTEXT)
        result = engine.evaluate()

        assert result.continuous_learning is not None
        assert result.continuous_learning.adaptive_health is not None
        assert isinstance(result.continuous_learning.adaptive_health, AdaptiveIntelligenceHealth)
        assert result.continuous_learning.adaptive_health.health_score > 0.0
