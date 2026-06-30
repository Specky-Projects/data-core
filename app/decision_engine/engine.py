"""Decision Engine — advisory-only structured decisions."""
from __future__ import annotations

import uuid

from app.capability_orchestrator.contracts import (
    CapabilityKind,
    CapabilityRegistration,
    CapabilityRequest,
    CapabilityResponse,
)
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.decision_engine.contracts import DecisionKind, DecisionRequest, DecisionResult, PolicyEvaluator
from app.scientific_identity.contract import stable_hash


class DecisionEngine:
    name = "decision_engine"

    CAPABILITY_DECIDE = "decision.decide"
    CAPABILITY_EVALUATE_POLICY = "decision.evaluate_policy"

    def __init__(self) -> None:
        self._policy = PolicyEvaluator()

    def register(self, orchestrator: CapabilityOrchestrator) -> None:
        caps = [
            CapabilityRegistration(
                capability_id=self.CAPABILITY_DECIDE,
                kind=CapabilityKind.DECISION,
                name="Decide",
                version="1.0.0",
                description="Advisory-only structured decision",
                input_schema={"context": "dict", "evidence": "list"},
                output_schema={"decision": "str", "rationale": "str", "confidence": "float"},
                dependencies=[],
                advisory_only=True,
                owner=self.name,
            ),
            CapabilityRegistration(
                capability_id=self.CAPABILITY_EVALUATE_POLICY,
                kind=CapabilityKind.DECISION,
                name="Evaluate Policy",
                version="1.0.0",
                description="Evaluates context against heuristic policies",
                input_schema={"context": "dict"},
                output_schema={"decision": "str"},
                dependencies=[],
                advisory_only=True,
                owner=self.name,
            ),
        ]
        for cap in caps:
            orchestrator.registry.register(cap)
            orchestrator.register_handler(cap.capability_id, self._dispatch(cap.capability_id))

    def _dispatch(self, capability_id: str):
        def handler(request: CapabilityRequest) -> CapabilityResponse:
            lineage_id = str(uuid.uuid4())
            outputs = self._handle(capability_id, request, lineage_id)
            sci_id = stable_hash({"capability": capability_id, "lineage": lineage_id})
            return CapabilityResponse(
                response_id=str(uuid.uuid4()),
                request_id=request.request_id,
                capability_id=capability_id,
                outputs=outputs,
                evidence=request.inputs.get("evidence", []),
                confidence=outputs.get("confidence", 0.5),
                advisory_only=True,
                lineage_id=lineage_id,
                scientific_id=sci_id,
            )
        return handler

    def _handle(self, capability_id: str, request: CapabilityRequest, lineage_id: str) -> dict:
        context = request.inputs.get("context", {})
        evidence = request.inputs.get("evidence", [])
        threshold = request.inputs.get("confidence_threshold", 0.7)

        kind = self._policy.evaluate(context, evidence, threshold)
        confidence = context.get("confidence", 0.5)

        rationale_map = {
            DecisionKind.ACT: f"Confidence {confidence:.2f} >= threshold {threshold:.2f}; evidence supports action",
            DecisionKind.DONT_ACT: f"Confidence {confidence:.2f} too low; do not act",
            DecisionKind.DEFER: f"Confidence borderline; defer pending more data",
            DecisionKind.INVESTIGATE: "Critical health condition detected; investigate first",
        }

        result = DecisionResult(
            decision_id=str(uuid.uuid4()),
            scientific_id=stable_hash({"decision": str(kind), "lineage": lineage_id}),
            lineage_id=lineage_id,
            decision=kind,
            rationale=rationale_map[kind],
            confidence=float(confidence) if 0.0 <= float(confidence) <= 1.0 else 0.5,
            evidence=evidence,
            advisory_only=True,
        )

        return {
            "decision": str(result.decision),
            "rationale": result.rationale,
            "confidence": result.confidence,
            "evidence": result.evidence,
            "advisory_only": True,
        }
