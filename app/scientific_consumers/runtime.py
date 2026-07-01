"""Runtime bundle for Phase 3.0 scientific consumers."""
from __future__ import annotations

from dataclasses import dataclass

from app.execution_ledger.contracts import ExecutionLedgerContract
from app.explainability_v2.contracts import ExplainabilityContract
from app.observation.contract import ObservationContract
from app.scientific_consumers.advisory_pipeline import (
    AdvisoryDecisionPipeline,
    build_pipeline_context,
)
from app.scientific_consumers.explainability_binding import build_explainability
from app.scientific_consumers.facts import DecisionFacts
from app.scientific_consumers.identity_binding import (
    build_identity_chain,
    decision_identity_id,
)
from app.scientific_consumers.learning_binding import (
    build_learning_evidence,
    build_learning_knowledge,
    build_learning_signal,
    build_learning_snapshot,
    build_learning_statistics,
    build_learning_timeline,
)
from app.scientific_consumers.ledger_binding import build_ledger
from app.scientific_consumers.observation_binding import build_observation
from app.scientific_identity.contract import ScientificIdentityChain
from app.scientific_pipeline.contracts import PipelineReplayManifest, PipelineState, PipelineTrace
from app.universal_learning.contracts import (
    LearningEvidence,
    LearningKnowledge,
    LearningSignal,
    LearningSnapshot,
    LearningStatistics,
    LearningTimeline,
)


@dataclass(frozen=True)
class ScientificConsumerRuntimeRecord:
    facts: DecisionFacts
    observation: ObservationContract
    identity_chain: ScientificIdentityChain
    pipeline_state: PipelineState
    pipeline_trace: PipelineTrace
    replay_manifest: PipelineReplayManifest
    explainability: ExplainabilityContract
    ledger: ExecutionLedgerContract
    learning_evidence: LearningEvidence
    learning_snapshot: LearningSnapshot
    learning_signal: LearningSignal
    learning_statistics: LearningStatistics
    learning_timeline: LearningTimeline
    learning_knowledge: tuple[LearningKnowledge, ...]

    @property
    def lineage_id(self) -> str:
        return self.facts.lineage_id

    def validate(self) -> list[str]:
        errors: list[str] = []
        errors.extend(self.observation.validate())
        for identity in self.identity_chain.entries:
            errors.extend(identity.validate())
        errors.extend(self.pipeline_trace.validate())
        errors.extend(self.replay_manifest.validate())
        errors.extend(self.explainability.validate())
        errors.extend(self.ledger.validate())
        errors.extend(self.learning_evidence.validate())
        errors.extend(self.learning_snapshot.validate())
        errors.extend(self.learning_signal.validate())
        errors.extend(self.learning_statistics.validate())
        errors.extend(self.learning_timeline.validate())
        for knowledge in self.learning_knowledge:
            errors.extend(knowledge.validate())
        return errors


class ScientificConsumerRuntime:
    """Pure materializer for scientific consumer artifacts."""

    def __init__(self, pipeline: AdvisoryDecisionPipeline | None = None) -> None:
        self.pipeline = pipeline or AdvisoryDecisionPipeline()

    def materialize(self, facts: DecisionFacts) -> ScientificConsumerRuntimeRecord:
        identity_chain = build_identity_chain(facts)
        observation = build_observation(facts, scientific_identity_id=decision_identity_id(facts))
        context = build_pipeline_context(facts)
        pipeline_state = self.pipeline.run(context)
        trace = self.pipeline.trace(context.pipeline_id)
        if trace is None:
            raise RuntimeError("pipeline trace missing after run")
        replay_manifest = self.pipeline.build_manifest(trace)
        return ScientificConsumerRuntimeRecord(
            facts=facts,
            observation=observation,
            identity_chain=identity_chain,
            pipeline_state=pipeline_state,
            pipeline_trace=trace,
            replay_manifest=replay_manifest,
            explainability=build_explainability(facts),
            ledger=build_ledger(facts),
            learning_evidence=build_learning_evidence(facts),
            learning_snapshot=build_learning_snapshot(facts),
            learning_signal=build_learning_signal(facts),
            learning_statistics=build_learning_statistics(facts),
            learning_timeline=build_learning_timeline(facts),
            learning_knowledge=build_learning_knowledge(facts),
        )
