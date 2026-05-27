"""SecurityAnalyzer — auth, API key, dry_run posture."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from app.operational_truth.dto import SecurityTruth, classify_score
from core.config import settings


def analyze_security() -> SecurityTruth:
    findings: list[str] = []
    now = datetime.now(timezone.utc)

    auth_enabled = settings.api_key_enabled
    api_key_protected = auth_enabled and bool(settings.api_key)

    if not auth_enabled:
        findings.append("auth_disabled: API key authentication is off")
    elif not settings.api_key:
        findings.append("auth_misconfigured: api_key_enabled=true but no key set")

    # Hardcoded secrets risk: check env for obvious defaults
    hardcoded_risk = False
    dangerous_values = {"password", "secret", "changeme", "admin", "data_core"}
    db_url = settings.database_url.lower()
    for val in dangerous_values:
        if f":{val}@" in db_url or f":{val}/" in db_url:
            hardcoded_risk = True
            findings.append(f"hardcoded_secret_risk: default credential pattern in DATABASE_URL")
            break

    # DRY_RUN check (relevant for poupi-crypto context)
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    # Score
    score = 100
    if not auth_enabled:
        env = settings.app_env.lower()
        if env in ("production", "prod"):
            score -= 30
            findings.append("auth_off_in_production: CRITICAL — enable API key auth")
        else:
            score -= 5  # advisory in dev/staging
    elif not api_key_protected:
        score -= 15

    if hardcoded_risk:
        score -= 20

    score = max(0, score)
    return SecurityTruth(
        score=score,
        status=classify_score(score),
        auth_enabled=auth_enabled,
        dry_run_active=dry_run,
        api_key_protected=api_key_protected,
        hardcoded_secrets_risk=hardcoded_risk,
        findings=findings,
        evaluated_at=now,
    )
