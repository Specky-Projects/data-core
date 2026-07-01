"""Business OS 6.0 — Phase 2 Universal Platform.

The Universal Adapter Layer. Every project (Mirror, Poupi Baby, Infrastructure,
Telegram, Affiliate) is observed here and projected onto the *same* Phase 1
Scientific Runtime — no engine, contract or runtime is duplicated.

Reuse policy (REUTILIZAR → ESTENDER → GENERALIZAR → CRIAR NOVO):
    * ObservationContract / ScientificIdentity / Explainability / Replay /
      PipelineTrace / ExecutionLedger / LearningFeed  -> reused verbatim.
    * ScientificConsumerRuntime.materialize()          -> reused verbatim.
    * CapabilityOrchestrator / CapabilityRegistry      -> reused verbatim.

Everything in this package operates strictly in:
    SHADOW_MODE = True   READ_ONLY = True   ADVISORY_ONLY = True

No adapter mutates a source system, and no project reaches an engine directly:
all traffic flows through an Adapter and the Capability Orchestrator.
"""
from __future__ import annotations

UNIVERSAL_PLATFORM_VERSION = "universal-platform-phase2-v1"

SHADOW_MODE = True
READ_ONLY = True
ADVISORY_ONLY = True
