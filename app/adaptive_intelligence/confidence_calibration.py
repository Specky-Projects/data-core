"""ConfidenceCalibrationEngine — bucket-by-bucket calibration analysis.

Buckets: 0-20, 21-40, 41-60, 61-80, 81-100 (by signal confidence score).

Advisory-only: reads TradingSignalOutcome rows, never writes.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.adaptive_intelligence.dto import (
    CalibrationBucket,
    ConfidenceCalibrationResult,
    EvaluationContext,
    LearningAuditTrail,
    ScientificVersionMetadata,
    build_confidence_evolution,
    build_decision_hash,
    build_feature_contributions,
    build_feature_provenance,
    build_scientific_lineage,
    compute_temporal_decay_from_evidence,
    derive_evaluation_context,
    filter_rows_for_context,
    _row_timestamp,
)
from app.modules.trading.validation.models import TradingSignalOutcome

logger = logging.getLogger(__name__)

# Confidence bucket definitions: (label, lower, upper)
_BUCKETS: list[tuple[str, int, int]] = [
    ("0-20",   0,  20),
    ("21-40", 21,  40),
    ("41-60", 41,  60),
    ("61-80", 61,  80),
    ("81-100", 81, 100),
]

# A slice is "well-calibrated" if realized win_rate ≥ this threshold
_CALIBRATED_WIN_RATE_THRESHOLD = 0.55

# Calibration gap thresholds for over/underconfidence flags
_OVERCONFIDENCE_GAP = -0.10   # realized << predicted  (negative gap)
_UNDERCONFIDENCE_GAP = 0.10   # realized >> predicted  (positive gap)


class _BucketAcc:
    """Raw accumulator for one confidence bucket."""

    __slots__ = ("confidence_sum", "wins", "losses", "returns", "evidence_ids", "timestamps")

    def __init__(self) -> None:
        self.confidence_sum: float = 0.0
        self.wins: int = 0
        self.losses: int = 0
        self.returns: list[float] = []
        self.evidence_ids: list[str] = []
        self.timestamps: list[float] = []

    def add(
        self,
        confidence: int,
        correct: bool,
        price_change_pct: float,
        evidence_id: str | None = None,
        row_timestamp: float | None = None,
    ) -> None:
        self.confidence_sum += confidence
        self.returns.append(price_change_pct)
        if evidence_id:
            self.evidence_ids.append(evidence_id)
        if row_timestamp is not None:
            self.timestamps.append(row_timestamp)
        if correct:
            self.wins += 1
        else:
            self.losses += 1

    @property
    def sample_size(self) -> int:
        return self.wins + self.losses

    @property
    def predicted_confidence_avg(self) -> float:
        n = self.sample_size
        return (self.confidence_sum / n) if n else 0.0

    @property
    def realized_win_rate(self) -> float:
        n = self.sample_size
        return (self.wins / n) if n else 0.0

    @property
    def avg_return_pct(self) -> float:
        return sum(self.returns) / len(self.returns) if self.returns else 0.0

    @property
    def return_stability(self) -> float:
        if len(self.returns) < 2:
            return 1.0 if self.returns else 0.0
        mean = self.avg_return_pct
        variance = sum((ret - mean) ** 2 for ret in self.returns) / len(self.returns)
        return max(0.0, min(1.0, 1.0 / (1.0 + variance ** 0.5)))


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _sample_confidence(sample_size: int, target: int = 30) -> float:
    return _clamp(sample_size / target)


def _build_learning_audit(
    *,
    label: str,
    previous_score: float,
    current_score: float,
    confidence: float,
    evidence_ids: list[str],
    positive_factors: list[str],
    negative_factors: list[str],
    rationale: str,
    timestamp,
    versions: ScientificVersionMetadata,
    provenance,
    decision_hash: str,
    confidence_evolution,
    feature_importance,
) -> LearningAuditTrail:
    delta = current_score - previous_score
    return LearningAuditTrail(
        evidence_ids=evidence_ids[:25],
        data_origin="trading_signal_outcomes",
        previous_score=round(previous_score, 4),
        current_score=round(current_score, 4),
        score_delta=round(delta, 4),
        confidence=round(confidence, 4),
        uncertainty=round(1.0 - confidence, 4),
        positive_factors=positive_factors,
        negative_factors=negative_factors,
        rationale=rationale,
        lineage=[
            "trading_signal_outcomes",
            "ConfidenceCalibrationEngine.evaluate",
            f"bucket:{label}",
        ],
        causal_history=[
            "confidence bucket aggregation",
            "realized win-rate comparison",
            "historical calibration scoring",
        ],
        score_change_reason=(
            "bucket became more reliable than neutral baseline"
            if delta > 0
            else "bucket became less reliable than neutral baseline"
            if delta < 0
            else "bucket remained at neutral baseline"
        ),
        timestamp=timestamp,
        originating_components=["ConfidenceCalibrationEngine"],
        historical_references=evidence_ids[:25],
        confidence_delta=round(current_score - previous_score, 4),
        versions=versions,
        provenance=provenance,
        decision_hash=decision_hash,
        scientific_lineage=build_scientific_lineage(
            entity_id=label,
            evidence_hash=provenance.evidence_hash,
            feature_hash=provenance.feature_hash,
            decision_hash=decision_hash,
            recommendation="CALIBRATE",
        ),
        confidence_evolution=confidence_evolution,
        feature_importance=feature_importance,
    )


class ConfidenceCalibrationEngine:
    """Analyse whether model confidence scores predict actual win rates.

    Parameters
    ----------
    db:
        Active SQLAlchemy Session.
    lookback_days:
        Calendar days of outcomes to include (default: 30).
    """

    def __init__(
        self,
        db: Session,
        lookback_days: int = 30,
        evaluation_context: EvaluationContext | None = None,
    ) -> None:
        self._db = db
        self._lookback_days = lookback_days
        self._evaluation_context = evaluation_context

    # ------------------------------------------------------------------

    def evaluate(self) -> ConfidenceCalibrationResult:
        all_rows: list[TradingSignalOutcome] = (
            self._db.query(TradingSignalOutcome)
            .filter(
                TradingSignalOutcome.outcome_correct.isnot(None),
                TradingSignalOutcome.confidence.isnot(None),
                TradingSignalOutcome.price_change_pct.isnot(None),
            )
            .all()
        )
        evaluation_context = derive_evaluation_context(
            all_rows,
            self._lookback_days,
            self._evaluation_context,
        )
        rows = filter_rows_for_context(all_rows, evaluation_context, self._lookback_days)
        versions = ScientificVersionMetadata()

        # Accumulate per bucket
        accs: dict[str, _BucketAcc] = {label: _BucketAcc() for label, _, _ in _BUCKETS}

        for row in rows:
            conf = int(row.confidence)  # type: ignore[arg-type]
            for label, lo, hi in _BUCKETS:
                if lo <= conf <= hi:
                    evidence_id = getattr(row, "id", None)
                    ts = _row_timestamp(row)
                    accs[label].add(
                        conf,
                        bool(row.outcome_correct),
                        float(row.price_change_pct),
                        str(evidence_id) if evidence_id is not None else None,
                        ts.timestamp() if ts is not None else None,
                    )
                    break

        # Build CalibrationBucket objects
        buckets: list[CalibrationBucket] = []
        calibrated_threshold: int | None = None

        for label, lo, hi in _BUCKETS:
            acc = accs[label]
            if acc.sample_size == 0:
                continue

            pred_avg = acc.predicted_confidence_avg
            realized = acc.realized_win_rate
            gap = realized - (pred_avg / 100.0)  # both on [0, 1] scale
            overconfident = gap < _OVERCONFIDENCE_GAP
            underconfident = gap > _UNDERCONFIDENCE_GAP
            sample_confidence = _sample_confidence(acc.sample_size)
            false_positive_rate = acc.losses / acc.sample_size if acc.sample_size else 0.0
            stability = acc.return_stability
            reliability = _clamp(
                (realized * 0.50)
                + (stability * 0.25)
                + (sample_confidence * 0.25)
            )
            # O6 fix: evidence-based temporal decay using actual bucket row timestamps
            if acc.timestamps:
                ref_ts = evaluation_context.evaluation_timestamp.timestamp()
                mean_age_days = max(0.0, (ref_ts - sum(acc.timestamps) / len(acc.timestamps)) / 86_400.0)
                temporal_decay = _clamp(1.0 - mean_age_days / 365.0, lower=0.25)
            else:
                temporal_decay = _clamp(1.0 - (self._lookback_days / 365.0), lower=0.25)
            positives = []
            negatives = []
            if realized >= _CALIBRATED_WIN_RATE_THRESHOLD:
                positives.append("bucket reached calibrated win-rate threshold")
            else:
                negatives.append("bucket below calibrated win-rate threshold")
            if not overconfident:
                positives.append("no overconfidence detected")
            else:
                negatives.append("overconfidence detected")
            if stability >= 0.7:
                positives.append("returns are historically stable")
            else:
                negatives.append("return variance reduces stability")
            features = {
                "predicted_confidence_avg": pred_avg,
                "realized_win_rate": realized,
                "false_positive_rate": false_positive_rate,
                "stability": stability,
                "sample_confidence": sample_confidence,
                "temporal_decay": temporal_decay,
            }
            provenance = build_feature_provenance(
                evaluation_context=evaluation_context,
                entity_id=label,
                features=features,
                evidence_ids=acc.evidence_ids,
                versions=versions,
            )
            confidence_evolution = build_confidence_evolution(
                initial=pred_avg / 100.0,
                calibrated=realized,
                learned=reliability,
                final=reliability * temporal_decay,
            )
            feature_importance = build_feature_contributions(
                {
                    "historical_accuracy": realized * 0.50,
                    "return_stability": stability * 0.25,
                    "historical_coverage": sample_confidence * 0.25,
                    "temporal_decay": temporal_decay * 0.10,
                }
            )
            decision_hash = build_decision_hash(
                evaluation_context=evaluation_context,
                versions=versions,
                provenance=provenance,
                entity_id=label,
                recommendation="CALIBRATE",
            )
            audit = _build_learning_audit(
                label=label,
                previous_score=0.5,
                current_score=reliability,
                confidence=sample_confidence,
                evidence_ids=acc.evidence_ids,
                positive_factors=positives,
                negative_factors=negatives,
                rationale=(
                    "Decision quality calibrated from predicted confidence, realized "
                    "accuracy, false-positive rate, stability and historical coverage."
                ),
                timestamp=evaluation_context.evaluation_timestamp,
                versions=versions,
                provenance=provenance,
                decision_hash=decision_hash,
                confidence_evolution=confidence_evolution,
                feature_importance=feature_importance,
            )

            buckets.append(CalibrationBucket(
                label=label,
                lower=lo,
                upper=hi,
                sample_size=acc.sample_size,
                predicted_confidence_avg=pred_avg,
                realized_win_rate=realized,
                calibration_gap=gap,
                avg_return_pct=acc.avg_return_pct,
                overconfident=overconfident,
                underconfident=underconfident,
                historical_accuracy=round(realized, 4),
                false_positive_rate=round(false_positive_rate, 4),
                temporal_quality=round(temporal_decay, 4),
                stability_score=round(stability, 4),
                reliability_score=round(reliability, 4),
                confidence_evolution_score=round(gap, 4),
                adaptive_weight=round(reliability * temporal_decay, 4),
                temporal_decay=round(temporal_decay, 4),
                evidence_ids=acc.evidence_ids[:25],
                learning_audit=audit,
                versions=versions,
                provenance=provenance,
                decision_hash=decision_hash,
                scientific_lineage=audit.scientific_lineage,
                confidence_evolution=confidence_evolution,
                feature_importance=feature_importance,
            ))

            # Track lowest bucket where win_rate meets threshold
            if realized >= _CALIBRATED_WIN_RATE_THRESHOLD:
                if calibrated_threshold is None or lo < calibrated_threshold:
                    calibrated_threshold = lo

        # Slope: linear regression of predicted_confidence_avg → realized_win_rate
        # Simple Pearson-slope without numpy (advisory context).
        slope = self._compute_slope(buckets)

        overconfidence_warning = any(b.overconfident for b in buckets)
        underconfidence_warning = any(b.underconfident for b in buckets)

        # well_calibrated: slope exists and positive, no extreme overconfidence
        well_calibrated = (slope is not None and slope > 0 and not overconfidence_warning)

        recommended_min_confidence = calibrated_threshold  # could be refined downstream

        total_outcomes = sum(b.sample_size for b in buckets)
        avg_reliability = (
            sum(b.reliability_score for b in buckets) / len(buckets)
            if buckets
            else 0.0
        )
        avg_false_positive = (
            sum(b.false_positive_rate for b in buckets) / len(buckets)
            if buckets
            else 0.0
        )

        logger.info(
            "adaptive.confidence_calibration evaluated",
            extra={
                "lookback_days": self._lookback_days,
                "total_outcomes": total_outcomes,
                "buckets": len(buckets),
                "calibrated_threshold": calibrated_threshold,
                "well_calibrated": well_calibrated,
                "slope": slope,
            },
        )

        return ConfidenceCalibrationResult(
            evaluated_at=evaluation_context.evaluation_timestamp,
            total_outcomes=total_outcomes,
            buckets=buckets,
            calibrated_threshold=calibrated_threshold,
            overall_calibration_slope=slope,
            well_calibrated=well_calibrated,
            overconfidence_warning=overconfidence_warning,
            underconfidence_warning=underconfidence_warning,
            recommended_min_confidence=recommended_min_confidence,
            historical_calibration={
                "decision_quality_score": round(avg_reliability, 4),
                "historical_accuracy": round(avg_reliability, 4),
                "false_positive_rate": round(avg_false_positive, 4),
                "confidence_evolution": {
                    bucket.label: bucket.confidence_evolution_score for bucket in buckets
                },
                "adaptive_weighting": {
                    bucket.label: bucket.adaptive_weight for bucket in buckets
                },
                "temporal_decay": {
                    bucket.label: bucket.temporal_decay for bucket in buckets
                },
                "evidence_ids": [
                    evidence_id
                    for bucket in buckets
                    for evidence_id in bucket.evidence_ids[:5]
                ],
            },
            evaluation_context=evaluation_context,
            versions=versions,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_slope(buckets: list[CalibrationBucket]) -> float | None:
        """Ordinary-least-squares slope: predicted_confidence_avg → realized_win_rate.

        Returns None if fewer than 2 buckets have data.
        """
        if len(buckets) < 2:
            return None

        xs = [b.predicted_confidence_avg for b in buckets]
        ys = [b.realized_win_rate for b in buckets]
        n = len(xs)
        x_mean = sum(xs) / n
        y_mean = sum(ys) / n

        numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(xs, ys, strict=False))
        denominator = sum((xi - x_mean) ** 2 for xi in xs)
        if denominator == 0:
            return None
        return numerator / denominator
