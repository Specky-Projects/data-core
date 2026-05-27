"""InfraAnalyzer — PostgreSQL + Redis health."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.operational_truth.dto import InfraTruth, classify_score
from core.config import settings


def analyze_infra(db: Session) -> InfraTruth:
    findings: list[str] = []
    now = datetime.now(timezone.utc)

    # PostgreSQL
    postgres_ok = False
    try:
        db.execute(text("SELECT 1"))
        postgres_ok = True
    except Exception as exc:
        findings.append(f"postgres_unavailable: {exc}")

    # Redis
    redis_ok = False
    redis_required = settings.cache_enabled
    try:
        import redis as redis_lib
        client = redis_lib.from_url(settings.redis_url, socket_connect_timeout=2, decode_responses=True)
        client.ping()
        redis_ok = True
    except Exception as exc:
        msg = f"redis_unreachable: {exc}"
        if redis_required:
            findings.append(msg)
        else:
            findings.append(f"redis_advisory: {exc}")

    # Score
    score = 100
    if not postgres_ok:
        score -= 60
    if not redis_ok and redis_required:
        score -= 30
    elif not redis_ok:
        score -= 5

    score = max(0, score)
    return InfraTruth(
        score=score,
        status=classify_score(score),
        postgres_ok=postgres_ok,
        redis_ok=redis_ok,
        redis_required=redis_required,
        findings=findings,
        evaluated_at=now,
    )
