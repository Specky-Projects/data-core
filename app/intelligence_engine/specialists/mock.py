"""MockAISpecialist — deterministic, for tests. Returns structured JSON."""
from __future__ import annotations

import uuid

from app.intelligence_engine.contracts import (
    AISpecialistKind,
    IntelligenceRequest,
    IntelligenceResult,
)

_ANALYSIS_BY_KIND: dict[AISpecialistKind, dict] = {
    AISpecialistKind.DIAGNOSTICS: {
        "root_cause": "synthetic-root-cause",
        "confidence": 0.8,
        "factors": ["factor-a", "factor-b"],
        "severity": "LOW",
    },
    AISpecialistKind.ARCHITECTURE: {
        "findings": ["no circular imports detected", "module boundaries clean"],
        "recommendations": ["consider splitting large modules"],
        "score": 0.85,
    },
    AISpecialistKind.PERFORMANCE: {
        "bottlenecks": [],
        "p99_latency_ms": 12.4,
        "throughput_rps": 850,
        "recommendations": ["cache observation results"],
    },
    AISpecialistKind.SECURITY: {
        "vulnerabilities": [],
        "risk_score": 0.1,
        "recommendations": ["rotate secrets quarterly"],
    },
    AISpecialistKind.COST: {
        "monthly_estimate_usd": 45.0,
        "biggest_cost_driver": "compute",
        "savings_opportunities": ["reduce idle containers"],
    },
    AISpecialistKind.STRATEGY: {
        "strategic_fit": "HIGH",
        "risks": ["market volatility"],
        "opportunities": ["expand crypto edge"],
    },
    AISpecialistKind.ANOMALY: {
        "anomalies_detected": 0,
        "baseline_deviation_pct": 2.1,
        "status": "NORMAL",
    },
}


class MockAISpecialist:
    kind = "mock"

    def analyze(self, request: IntelligenceRequest) -> IntelligenceResult:
        analysis = _ANALYSIS_BY_KIND.get(
            request.specialist_kind,
            {"result": "unknown-kind", "kind": str(request.specialist_kind)},
        )
        return IntelligenceResult(
            result_id=str(uuid.uuid4()),
            request_id=request.request_id,
            specialist_kind=request.specialist_kind,
            analysis=analysis,
            confidence=0.85,
            evidence=["mock-evidence-001"],
            recommendations=["review findings above"],
            advisory_only=True,
        )
