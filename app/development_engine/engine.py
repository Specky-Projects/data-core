"""Development Engine — software development advisory capabilities."""
from __future__ import annotations

import uuid

from app.capability_orchestrator.contracts import (
    CapabilityKind,
    CapabilityRegistration,
    CapabilityRequest,
    CapabilityResponse,
)
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.development_engine.capabilities.adr_generator import ADRGeneratorCapability
from app.development_engine.capabilities.arch_review import ArchReviewCapability
from app.development_engine.capabilities.doc_generator import DocGeneratorCapability
from app.development_engine.capabilities.migration_planner import MigrationPlannerCapability
from app.development_engine.capabilities.reuse_checker import ReuseCheckerCapability
from app.development_engine.capabilities.roadmap_generator import RoadmapGeneratorCapability
from app.development_engine.capabilities.specification import SpecificationCapability
from app.development_engine.capabilities.technical_debt import TechnicalDebtCapability
from app.development_engine.capabilities.test_planner import TestPlannerCapability
from app.scientific_identity.contract import stable_hash


class DevelopmentEngine:
    name = "development_engine"

    CAPABILITY_REUSE_CHECK = "development.reuse_check"
    CAPABILITY_ARCH_REVIEW = "development.arch_review"
    CAPABILITY_TECH_DEBT = "development.tech_debt"
    CAPABILITY_ADR = "development.adr"
    CAPABILITY_SPEC = "development.spec"
    CAPABILITY_MIGRATION = "development.migration"
    CAPABILITY_TEST_PLAN = "development.test_plan"
    CAPABILITY_DOC = "development.doc"
    CAPABILITY_ROADMAP = "development.roadmap"

    def __init__(self) -> None:
        self._caps_impl = {
            self.CAPABILITY_REUSE_CHECK: ReuseCheckerCapability(),
            self.CAPABILITY_ARCH_REVIEW: ArchReviewCapability(),
            self.CAPABILITY_TECH_DEBT: TechnicalDebtCapability(),
            self.CAPABILITY_ADR: ADRGeneratorCapability(),
            self.CAPABILITY_SPEC: SpecificationCapability(),
            self.CAPABILITY_MIGRATION: MigrationPlannerCapability(),
            self.CAPABILITY_TEST_PLAN: TestPlannerCapability(),
            self.CAPABILITY_DOC: DocGeneratorCapability(),
            self.CAPABILITY_ROADMAP: RoadmapGeneratorCapability(),
        }

    def register(self, orchestrator: CapabilityOrchestrator) -> None:
        definitions = [
            (self.CAPABILITY_REUSE_CHECK, "Reuse Checker", "REUSE→EXTEND→GENERALIZE→CREATE_NEW"),
            (self.CAPABILITY_ARCH_REVIEW, "Architecture Review", "Reviews module architecture"),
            (self.CAPABILITY_TECH_DEBT, "Technical Debt", "Identifies technical debt items"),
            (self.CAPABILITY_ADR, "ADR Generator", "Generates Architecture Decision Records"),
            (self.CAPABILITY_SPEC, "Specification Generator", "Generates component specifications"),
            (self.CAPABILITY_MIGRATION, "Migration Planner", "Plans database migrations"),
            (self.CAPABILITY_TEST_PLAN, "Test Planner", "Plans test coverage"),
            (self.CAPABILITY_DOC, "Documentation Generator", "Generates module documentation"),
            (self.CAPABILITY_ROADMAP, "Roadmap Generator", "Generates development roadmap"),
        ]
        for cap_id, name, description in definitions:
            cap = CapabilityRegistration(
                capability_id=cap_id,
                kind=CapabilityKind.DEVELOPMENT,
                name=name,
                version="1.0.0",
                description=description,
                input_schema={},
                output_schema={},
                dependencies=[],
                advisory_only=True,
                owner=self.name,
            )
            orchestrator.registry.register(cap)
            orchestrator.register_handler(cap_id, self._dispatch(cap_id))

    def _dispatch(self, capability_id: str):
        def handler(request: CapabilityRequest) -> CapabilityResponse:
            lineage_id = str(uuid.uuid4())
            impl = self._caps_impl.get(capability_id)
            outputs = impl.execute(request.inputs) if impl else {}
            sci_id = stable_hash({"capability": capability_id, "lineage": lineage_id})
            return CapabilityResponse(
                response_id=str(uuid.uuid4()),
                request_id=request.request_id,
                capability_id=capability_id,
                outputs=outputs,
                evidence=[],
                confidence=0.9,
                advisory_only=True,
                lineage_id=lineage_id,
                scientific_id=sci_id,
            )
        return handler
