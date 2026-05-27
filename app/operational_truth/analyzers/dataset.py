"""DatasetTruthAnalyzer — freshness, integrity, lag, schema drift."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.operational_truth.dto import DatasetTruth, classify_score


def _age_seconds(ts: datetime | None, now: datetime) -> int | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0, int((now - ts).total_seconds()))


def _lag_seconds(newer: datetime | None, older: datetime | None) -> int | None:
    if newer is None or older is None:
        return None
    for t in [newer, older]:
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
    newer = newer.replace(tzinfo=timezone.utc) if newer.tzinfo is None else newer
    older = older.replace(tzinfo=timezone.utc) if older.tzinfo is None else older
    return max(0, int((newer - older).total_seconds()))


def analyze_dataset(db: Session) -> DatasetTruth:
    findings: list[str] = []
    now = datetime.now(timezone.utc)

    # ── Raw collection freshness ───────────────────────────────────────────────
    crypto_raw_age: int | None = None
    raw_pending = 0
    raw_failed = 0
    try:
        from app.raw.models import RawCollection
        latest_crypto_raw = (
            db.query(func.max(RawCollection.collected_at))
            .filter(RawCollection.module == "crypto")
            .scalar()
        )
        crypto_raw_age = _age_seconds(latest_crypto_raw, now)
        if crypto_raw_age is None:
            findings.append("crypto_raw_missing: no records found")
        elif crypto_raw_age > 86400:
            findings.append(f"crypto_raw_stale: {crypto_raw_age}s old (>24h)")
        elif crypto_raw_age > 3600:
            findings.append(f"crypto_raw_aging: {crypto_raw_age}s old (>1h)")

        raw_pending = (
            db.query(RawCollection)
            .filter(RawCollection.processing_status == "normalization_pending")
            .count()
        )
        raw_failed = (
            db.query(RawCollection)
            .filter(RawCollection.processing_status == "normalization_failed")
            .count()
        )
        if raw_failed > 0:
            findings.append(f"raw_failed_records: {raw_failed}")
    except Exception as exc:
        findings.append(f"raw_query_error: {exc}")

    # ── Normalization lag ──────────────────────────────────────────────────────
    crypto_norm_lag: int | None = None
    try:
        from app.normalization.models import NormalizedMarketCandle
        from app.raw.models import RawCollection as RC
        latest_raw = (
            db.query(func.max(RC.collected_at)).filter(RC.module == "crypto").scalar()
        )
        latest_norm = db.query(func.max(NormalizedMarketCandle.normalized_at)).scalar()
        crypto_norm_lag = _lag_seconds(latest_raw, latest_norm)
        if crypto_norm_lag is not None and crypto_norm_lag > 7200:
            findings.append(f"crypto_normalization_stale: lag {crypto_norm_lag}s")
        elif crypto_norm_lag is not None and crypto_norm_lag > 3600:
            findings.append(f"crypto_normalization_lagging: lag {crypto_norm_lag}s")
    except Exception as exc:
        findings.append(f"normalization_lag_query_error: {exc}")

    # ── Analytics lag ─────────────────────────────────────────────────────────
    crypto_analytics_lag: int | None = None
    try:
        from app.analytics.models import TradingAnalytics
        from app.raw.models import RawCollection as RC2
        latest_raw2 = (
            db.query(func.max(RC2.collected_at)).filter(RC2.module == "crypto").scalar()
        )
        latest_analytics = db.query(func.max(TradingAnalytics.calculated_at)).scalar()
        crypto_analytics_lag = _lag_seconds(latest_raw2, latest_analytics)
        if crypto_analytics_lag is not None and crypto_analytics_lag > 7200:
            findings.append(f"crypto_analytics_stale: lag {crypto_analytics_lag}s")
    except Exception as exc:
        findings.append(f"analytics_lag_query_error: {exc}")

    # ── Score ──────────────────────────────────────────────────────────────────
    ingestion_lag_critical = (
        crypto_raw_age is None
        or crypto_raw_age > 86400
        or (crypto_norm_lag is not None and crypto_norm_lag > 14400)
    )

    score = 100
    if crypto_raw_age is None:
        score -= 40
    elif crypto_raw_age > 86400:
        score -= 35
    elif crypto_raw_age > 3600:
        score -= 10

    if crypto_norm_lag is not None and crypto_norm_lag > 7200:
        score -= 25
    elif crypto_norm_lag is not None and crypto_norm_lag > 3600:
        score -= 10

    if crypto_analytics_lag is not None and crypto_analytics_lag > 7200:
        score -= 15
    elif crypto_analytics_lag is not None and crypto_analytics_lag > 3600:
        score -= 5

    if raw_failed > 100:
        score -= 20
    elif raw_failed > 0:
        score -= 5

    if raw_pending > 500:
        score -= 15
    elif raw_pending > 100:
        score -= 5

    score = max(0, score)
    return DatasetTruth(
        score=score,
        status=classify_score(score),
        crypto_raw_age_seconds=crypto_raw_age,
        crypto_normalization_lag_seconds=crypto_norm_lag,
        crypto_analytics_lag_seconds=crypto_analytics_lag,
        raw_pending=raw_pending,
        raw_failed=raw_failed,
        schema_drift_detected=False,  # placeholder — requires schema history tracking
        append_only_violations=0,     # placeholder — requires audit log
        ingestion_lag_critical=ingestion_lag_critical,
        findings=findings,
        evaluated_at=now,
    )
