"""StrategyFeedbackEngine — per-slice win rate, expectancy, drawdown analysis.

Advisory-only: reads TradingSignalOutcome rows, never writes trading decisions.

Slice key: "{symbol}|{timeframe}|{regime or 'any'}|{signal}"
"""

from __future__ import annotations

import logging
from collections import defaultdict

from sqlalchemy.orm import Session

from app.adaptive_intelligence.dto import (
    ContinuousLearningProfile,
    ContinuousLearningSignal,
    EvaluationContext,
    LearningAuditTrail,
    Recommendation,
    ScientificVersionMetadata,
    StrategyFeedbackResult,
    StrategySlice,
    _classify_recommendation,
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
)
from app.modules.trading.validation.models import TradingSignalOutcome

logger = logging.getLogger(__name__)


# ── Internal accumulator ───────────────────────────────────────────────────────

class _Acc:
    """Accumulates raw numbers for one slice."""

    __slots__ = (
        "wins", "losses", "returns", "drawdowns",
        "gross_profit", "gross_loss", "mfe", "mae", "evidence_ids", "validation_lags_days",
    )

    def __init__(self) -> None:
        self.wins: int = 0
        self.losses: int = 0
        self.returns: list[float] = []
        self.drawdowns: list[float] = []
        self.gross_profit: float = 0.0
        self.gross_loss: float = 0.0
        self.mfe: list[float] = []
        self.mae: list[float] = []
        self.evidence_ids: list[str] = []
        self.validation_lags_days: list[float] = []

    # ------------------------------------------------------------------

    def add(self, outcome: TradingSignalOutcome) -> None:
        ret = float(outcome.price_change_pct or 0.0)
        self.returns.append(ret)
        outcome_id = getattr(outcome, "id", None)
        if outcome_id is not None:
            self.evidence_ids.append(str(outcome_id))
        if ret > 0:
            self.gross_profit += ret
            self.wins += 1
        else:
            self.gross_loss += abs(ret)
            self.losses += 1
        # worst adverse excursion per outcome → drawdown proxy
        adverse = float(outcome.max_adverse_pct or 0.0)
        self.drawdowns.append(abs(adverse))
        if outcome.max_favorable_pct is not None:
            self.mfe.append(float(outcome.max_favorable_pct))
        if outcome.max_adverse_pct is not None:
            self.mae.append(abs(float(outcome.max_adverse_pct)))
        validation_at = (
            getattr(outcome, "outcome_at", None)
            or getattr(outcome, "evaluated_at", None)
        )
        signal_at = getattr(outcome, "signal_at", None)
        if validation_at is not None and signal_at is not None:
            try:
                self.validation_lags_days.append(
                    max((validation_at - signal_at).total_seconds() / 86_400.0, 0.0)
                )
            except Exception:
                pass

    # ------------------------------------------------------------------

    @property
    def sample_size(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        n = self.sample_size
        return self.wins / n if n else 0.0

    @property
    def avg_return_pct(self) -> float:
        return sum(self.returns) / len(self.returns) if self.returns else 0.0

    @property
    def expectancy(self) -> float:
        """win_rate * avg_win - loss_rate * avg_loss."""
        n = self.sample_size
        if n == 0:
            return 0.0
        avg_win = (self.gross_profit / self.wins) if self.wins else 0.0
        avg_loss = (self.gross_loss / self.losses) if self.losses else 0.0
        return self.win_rate * avg_win - (1 - self.win_rate) * avg_loss

    @property
    def max_drawdown_pct(self) -> float:
        return max(self.drawdowns) if self.drawdowns else 0.0

    @property
    def profit_factor(self) -> float | None:
        if self.gross_loss == 0:
            return None  # no losses → undefined, not ∞
        return self.gross_profit / self.gross_loss

    @property
    def avg_mfe_pct(self) -> float | None:
        return sum(self.mfe) / len(self.mfe) if self.mfe else None

    @property
    def avg_mae_pct(self) -> float | None:
        return sum(self.mae) / len(self.mae) if self.mae else None

    @property
    def avg_validation_lag_days(self) -> float | None:
        return (
            sum(self.validation_lags_days) / len(self.validation_lags_days)
            if self.validation_lags_days
            else None
        )


# ── Slice key helper ───────────────────────────────────────────────────────────

def _slice_key(symbol: str, timeframe: str, regime: str | None, signal: str) -> str:
    return f"{symbol}|{timeframe}|{regime or 'any'}|{signal}"


def _build_reason(
    rec: Recommendation,
    win_rate: float,
    expectancy: float,
    profit_factor: float | None,
    sample_size: int,
) -> str:
    pf_str = f"{profit_factor:.2f}" if profit_factor is not None else "N/A"
    base = (
        f"n={sample_size} wr={win_rate:.1%} "
        f"exp={expectancy:.4f} pf={pf_str}"
    )
    notes: dict[str, str] = {
        "OBSERVE_ONLY": "insufficient sample to conclude",
        "BOOST": "strong win rate, positive expectancy, healthy profit factor",
        "KEEP": "acceptable win rate and non-negative expectancy",
        "DISABLE": "poor win rate + negative expectancy + adequate sample",
        "THROTTLE": "marginal performance — monitor closely",
    }
    return f"{notes.get(rec, '')} ({base})"


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _score_from_return(value: float) -> float:
    return _clamp((value + 2.0) / 4.0)


def _sample_confidence(sample_size: int, target: int = 30) -> float:
    return _clamp(sample_size / target)


def _build_learning_audit(
    *,
    dimension: str,
    entity_id: str,
    data_origin: str,
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
        data_origin=data_origin,
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
            "StrategyFeedbackEngine.evaluate",
            f"dimension:{dimension}",
            f"entity:{entity_id}",
        ],
        causal_history=[
            "historical outcome replay",
            "slice-level aggregation",
            "recommendation classification",
        ],
        score_change_reason=(
            "historical evidence improved the score"
            if delta > 0
            else "historical evidence reduced the score"
            if delta < 0
            else "historical evidence preserved the baseline score"
        ),
        timestamp=timestamp,
        originating_components=["StrategyFeedbackEngine"],
        historical_references=evidence_ids[:25],
        confidence_delta=round(current_score - previous_score, 4),
        versions=versions,
        provenance=provenance,
        decision_hash=decision_hash,
        scientific_lineage=build_scientific_lineage(
            entity_id=entity_id,
            evidence_hash=provenance.evidence_hash,
            feature_hash=provenance.feature_hash,
            decision_hash=decision_hash,
            recommendation=dimension,
        ),
        confidence_evolution=confidence_evolution,
        feature_importance=feature_importance,
    )


# ── Engine ─────────────────────────────────────────────────────────────────────

class StrategyFeedbackEngine:
    """Analyses historical TradingSignalOutcome rows by slice.

    Parameters
    ----------
    db:
        Active SQLAlchemy Session.
    lookback_days:
        How many calendar days of outcomes to include (default: 30).
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

    def evaluate(self) -> StrategyFeedbackResult:
        all_rows: list[TradingSignalOutcome] = (
            self._db.query(TradingSignalOutcome)
            .filter(
                TradingSignalOutcome.outcome_correct.isnot(None),
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

        # Accumulate per slice
        accs: dict[str, _Acc] = defaultdict(_Acc)
        meta: dict[str, tuple[str, str, str | None, str]] = {}  # key → (symbol, tf, regime, signal)

        for row in rows:
            key = _slice_key(row.symbol, row.timeframe, row.regime, row.signal)
            accs[key].add(row)
            meta[key] = (row.symbol, row.timeframe, row.regime, row.signal)

        # Build slices
        slices: list[StrategySlice] = []
        summary: dict[str, int] = {
            "BOOST": 0, "KEEP": 0, "THROTTLE": 0, "DISABLE": 0, "OBSERVE_ONLY": 0,
        }
        top_performers: list[str] = []
        underperformers: list[str] = []
        source_quality: list[ContinuousLearningSignal] = []
        discovery_quality: list[ContinuousLearningSignal] = []
        economic_learning: list[ContinuousLearningSignal] = []

        for key, acc in accs.items():
            symbol, timeframe, regime, signal = meta[key]
            rec = _classify_recommendation(
                acc.win_rate, acc.expectancy, acc.profit_factor, acc.sample_size
            )
            reason = _build_reason(
                rec, acc.win_rate, acc.expectancy, acc.profit_factor, acc.sample_size
            )
            sample_confidence = _sample_confidence(acc.sample_size)
            impact_score = _score_from_return(acc.avg_return_pct)
            reliability_score = _clamp(
                (acc.win_rate * 0.45)
                + (impact_score * 0.35)
                + (sample_confidence * 0.20)
            )
            priority_score = _clamp(
                reliability_score * 0.55
                + (1.0 if rec == "BOOST" else 0.65 if rec == "KEEP" else 0.35) * 0.30
                + sample_confidence * 0.15
            )
            novelty_score = _clamp(1.0 - (acc.sample_size / 100.0))
            duplicate_risk = _clamp(1.0 - novelty_score)
            accepted = acc.wins if rec in ("BOOST", "KEEP") else 0
            discarded = acc.losses if rec in ("THROTTLE", "DISABLE") else 0
            positives = []
            negatives = []
            if acc.win_rate >= 0.5:
                positives.append("historical win rate at or above acceptance threshold")
            else:
                negatives.append("historical win rate below acceptance threshold")
            if acc.expectancy >= 0:
                positives.append("non-negative historical expectancy")
            else:
                negatives.append("negative historical expectancy")
            if sample_confidence < 1.0:
                negatives.append("limited historical coverage")
            if acc.profit_factor and acc.profit_factor >= 1.5:
                positives.append("profit factor supports reinforcement")
            features = {
                "win_rate": acc.win_rate,
                "expectancy": acc.expectancy,
                "profit_factor": acc.profit_factor,
                "sample_confidence": sample_confidence,
                "impact_score": impact_score,
                "recommendation": rec,
            }
            provenance = build_feature_provenance(
                evaluation_context=evaluation_context,
                entity_id=key,
                features=features,
                evidence_ids=acc.evidence_ids,
                versions=versions,
            )
            confidence_evolution = build_confidence_evolution(
                initial=0.5,
                calibrated=reliability_score,
                learned=priority_score,
                final=priority_score,
            )
            feature_importance = build_feature_contributions(
                {
                    "historical_accuracy": acc.win_rate * 0.45,
                    "economic_impact": impact_score * 0.35,
                    "historical_coverage": sample_confidence * 0.20,
                }
            )
            decision_hash = build_decision_hash(
                evaluation_context=evaluation_context,
                versions=versions,
                provenance=provenance,
                entity_id=key,
                recommendation=rec,
            )
            audit = _build_learning_audit(
                dimension="discovery_quality",
                entity_id=key,
                data_origin="trading_signal_outcomes",
                previous_score=0.5,
                current_score=priority_score,
                confidence=sample_confidence,
                evidence_ids=acc.evidence_ids,
                positive_factors=positives,
                negative_factors=negatives,
                rationale=reason,
                timestamp=evaluation_context.evaluation_timestamp,
                versions=versions,
                provenance=provenance,
                decision_hash=decision_hash,
                confidence_evolution=confidence_evolution,
                feature_importance=feature_importance,
            )
            slices.append(StrategySlice(
                symbol=symbol,
                timeframe=timeframe,
                regime=regime,
                signal=signal,
                sample_size=acc.sample_size,
                win_rate=acc.win_rate,
                avg_return_pct=acc.avg_return_pct,
                expectancy=acc.expectancy,
                max_drawdown_pct=acc.max_drawdown_pct,
                profit_factor=acc.profit_factor,
                avg_mfe_pct=acc.avg_mfe_pct,
                avg_mae_pct=acc.avg_mae_pct,
                recommendation=rec,
                recommendation_reason=reason,
                priority_score=round(priority_score, 4),
                novelty_score=round(novelty_score, 4),
                duplicate_risk=round(duplicate_risk, 4),
                impact_score=round(impact_score, 4),
                relevance_score=round(reliability_score, 4),
                accepted_opportunities=accepted,
                discarded_opportunities=discarded,
                time_to_validation_days=(
                    round(acc.avg_validation_lag_days, 4)
                    if acc.avg_validation_lag_days is not None
                    else None
                ),
                evidence_ids=acc.evidence_ids[:25],
                learning_audit=audit,
                versions=versions,
                provenance=provenance,
                decision_hash=decision_hash,
                scientific_lineage=audit.scientific_lineage,
                confidence_evolution=confidence_evolution,
                feature_importance=feature_importance,
            ))
            source_signal = ContinuousLearningSignal(
                dimension="source_quality",
                entity_id=f"{symbol}|{timeframe}",
                entity_type="source_proxy",
                current_confidence=round(reliability_score, 4),
                uncertainty=round(1.0 - sample_confidence, 4),
                evidence_ids=acc.evidence_ids[:25],
                data_origin="trading_signal_outcomes",
                positive_factors=positives,
                negative_factors=negatives,
                rationale=(
                    "Source quality inferred from historical signal accuracy, "
                    "false-positive behavior, return stability and sample coverage."
                ),
                audit_trail=_build_learning_audit(
                    dimension="source_quality",
                    entity_id=f"{symbol}|{timeframe}",
                    data_origin="trading_signal_outcomes",
                    previous_score=0.5,
                    current_score=reliability_score,
                    confidence=sample_confidence,
                    evidence_ids=acc.evidence_ids,
                    positive_factors=positives,
                    negative_factors=negatives,
                    rationale="Adaptive source proxy quality recalibrated from outcomes.",
                    timestamp=evaluation_context.evaluation_timestamp,
                    versions=versions,
                    provenance=provenance,
                    decision_hash=decision_hash,
                    confidence_evolution=confidence_evolution,
                    feature_importance=feature_importance,
                ),
                versions=versions,
                provenance=provenance,
                decision_hash=decision_hash,
                scientific_lineage=audit.scientific_lineage,
                confidence_evolution=confidence_evolution,
                feature_importance=feature_importance,
            )
            discovery_signal = ContinuousLearningSignal(
                dimension="discovery_quality",
                entity_id=key,
                entity_type="strategy_slice",
                current_confidence=round(priority_score, 4),
                uncertainty=round(1.0 - sample_confidence, 4),
                evidence_ids=acc.evidence_ids[:25],
                data_origin="trading_signal_outcomes",
                positive_factors=positives,
                negative_factors=negatives,
                rationale=reason,
                audit_trail=audit,
                versions=versions,
                provenance=provenance,
                decision_hash=decision_hash,
                scientific_lineage=audit.scientific_lineage,
                confidence_evolution=confidence_evolution,
                feature_importance=feature_importance,
            )
            economic_score = _clamp((acc.expectancy + 2.0) / 4.0)
            economic_confidence = build_confidence_evolution(
                initial=0.5,
                calibrated=reliability_score,
                learned=economic_score,
                final=economic_score,
            )
            economic_learning.append(ContinuousLearningSignal(
                dimension="economic_learning",
                entity_id=key,
                entity_type="strategy_slice",
                current_confidence=round(economic_score, 4),
                uncertainty=round(1.0 - sample_confidence, 4),
                evidence_ids=acc.evidence_ids[:25],
                data_origin="trading_signal_outcomes",
                positive_factors=positives,
                negative_factors=negatives,
                rationale=(
                    "Economic learning estimated from realized return, expectancy, "
                    "profit factor and opportunity cost proxy."
                ),
                audit_trail=_build_learning_audit(
                    dimension="economic_learning",
                    entity_id=key,
                    data_origin="trading_signal_outcomes",
                    previous_score=0.5,
                    current_score=economic_score,
                    confidence=sample_confidence,
                    evidence_ids=acc.evidence_ids,
                    positive_factors=positives,
                    negative_factors=negatives,
                    rationale="Economic score recalibrated from realized historical outcomes.",
                    timestamp=evaluation_context.evaluation_timestamp,
                    versions=versions,
                    provenance=provenance,
                    decision_hash=decision_hash,
                    confidence_evolution=economic_confidence,
                    feature_importance=feature_importance,
                ),
                versions=versions,
                provenance=provenance,
                decision_hash=decision_hash,
                scientific_lineage=audit.scientific_lineage,
                confidence_evolution=economic_confidence,
                feature_importance=feature_importance,
            ))
            source_quality.append(source_signal)
            discovery_quality.append(discovery_signal)
            summary[rec] = summary.get(rec, 0) + 1
            if rec == "BOOST":
                top_performers.append(key)
            elif rec in ("THROTTLE", "DISABLE"):
                underperformers.append(key)

        total_samples = sum(acc.sample_size for acc in accs.values())
        avg_confidence = (
            sum(signal.current_confidence for signal in discovery_quality) / len(discovery_quality)
            if discovery_quality
            else 0.0
        )
        coverage_confidence = _sample_confidence(total_samples, target=100)
        drift = compute_longitudinal_drift(all_rows, evaluation_context)
        saturation = compute_learning_saturation(drift)
        all_evidence_ids = sorted(
            {evidence_id for acc in accs.values() for evidence_id in acc.evidence_ids}
        )
        feature_provenance_score = min(1.0, len(all_evidence_ids) / 10.0) if all_evidence_ids else 0.0
        health = compute_scientific_health(
            evaluation_context=evaluation_context,
            versions=versions,
            evidence_ids=all_evidence_ids,
            drift=drift,
            saturation=saturation,
            explainability_present=True,
            calibration_quality=avg_confidence,
            confidence_consistency=coverage_confidence,
            feature_provenance_score=feature_provenance_score,
        )
        freshness = compute_freshness(all_rows, evaluation_context)
        profile_hash = build_decision_hash(
            evaluation_context=evaluation_context,
            versions=versions,
            provenance=build_feature_provenance(
                evaluation_context=evaluation_context,
                entity_id="continuous_learning_profile",
                features={
                    "avg_confidence": avg_confidence,
                    "coverage_confidence": coverage_confidence,
                    "total_samples": total_samples,
                },
                evidence_ids=all_evidence_ids,
                versions=versions,
            ),
            entity_id="continuous_learning_profile",
            recommendation="PROFILE",
        )
        continuous_learning = ContinuousLearningProfile(
            evaluated_at=evaluation_context.evaluation_timestamp,
            lookback_days=self._lookback_days,
            coverage_sample_size=total_samples,
            source_quality=source_quality,
            discovery_quality=discovery_quality,
            economic_learning=economic_learning,
            feedback={
                "explicit_feedback": {
                    "accepted_opportunities": sum(s.accepted_opportunities for s in slices),
                    "discarded_opportunities": sum(s.discarded_opportunities for s in slices),
                },
                "implicit_feedback": {
                    "top_performer_count": len(top_performers),
                    "underperformer_count": len(underperformers),
                    "observe_only_count": summary.get("OBSERVE_ONLY", 0),
                },
                "reinforcement_scoring": round(avg_confidence, 4),
                "adaptive_weighting": {
                    "historical_accuracy": 0.45,
                    "economic_impact": 0.35,
                    "historical_coverage": 0.20,
                },
                "temporal_decay": "lookback_window_days",
                "historical_calibration": "slice-level historical outcome replay",
            },
            self_evaluation={
                "current_confidence": round(avg_confidence, 4),
                "uncertainty": round(1.0 - coverage_confidence, 4),
                "evidence_count": total_samples,
                "positive_factors": [
                    "uses existing TradingSignalOutcome history",
                    "keeps learning advisory and read-only",
                    "records evidence IDs and score deltas",
                ],
                "negative_factors": (
                    ["limited historical coverage"]
                    if coverage_confidence < 1.0
                    else []
                ),
                "justification": (
                    "Continuous learning profile derived without new tables "
                    "or runtime side effects."
                ),
                "evolution_history": [
                    "Business OS 1.2 closed loop",
                    "Business OS 1.3 Stage 3 adaptive continuous learning",
                ],
                "score_change_reason": (
                    "historical outcomes recalibrated slice/source/economic scores"
                ),
            },
            observability={
                "confidence_evolution": round(avg_confidence, 4),
                "learning_rate": round(len(discovery_quality) / max(total_samples, 1), 4),
                "convergence_rate": round(coverage_confidence, 4),
                "drift": round(1.0 - avg_confidence, 4),
                "stability": round(coverage_confidence, 4),
                "historical_coverage": round(coverage_confidence, 4),
            },
            evaluation_context=evaluation_context,
            versions=versions,
            decision_hash=profile_hash,
            longitudinal_drift=drift,
            learning_saturation=saturation,
            scientific_health=health,
            freshness=freshness,
        )

        logger.info(
            "adaptive.strategy_feedback evaluated",
            extra={
                "lookback_days": self._lookback_days,
                "total_outcomes": len(rows),
                "slices": len(slices),
                "summary": summary,
            },
        )

        return StrategyFeedbackResult(
            evaluated_at=evaluation_context.evaluation_timestamp,
            lookback_days=self._lookback_days,
            total_outcomes=len(rows),
            slices=slices,
            summary=summary,
            top_performers=top_performers,
            underperformers=underperformers,
            continuous_learning=continuous_learning,
        )
