"""Scientific Runtime Consumers — Phase 3.0.

Wires the platform's real consumers (Mirror, Poupi Baby, Business OS) onto the
already-existing canonical scientific contracts. This package introduces NO new
contracts, engines or frameworks — it only *consumes* what Phases 2.1/2.2/2.3
and Business OS 6.0 Phase 1A already built.

Invariants enforced here:
  * read-only      — consumers never mutate the decision they observe;
  * advisory-only  — nothing in this package can trigger execution;
  * deterministic  — identical input always yields identical scientific_ids/hashes;
  * replayable     — every trace can be reconstructed from a ReplayManifest;
  * auditable      — full Observation→Identity→…→Learning chain is materialised.

The Mirror keeps deciding exactly as today. The scientific layer only observes
and records. Poupi Baby produces supervised recommendations only — never an
autonomous execution or publication.
"""
from __future__ import annotations

from app.scientific_consumers.business_os_runtime import build_business_os_registry
from app.scientific_consumers.mirror import (
    MirrorScientificCoverage,
    MirrorScientificObserver,
    MirrorScientificRuntimeBinding,
)
from app.scientific_consumers.poupi_baby import PoupiBabyScientificConsumer
from app.scientific_consumers.runtime import ScientificConsumerRuntime, ScientificConsumerRuntimeRecord

CONSUMERS_VERSION = "scientific-consumers-v1"

__all__ = [
    "CONSUMERS_VERSION",
    "MirrorScientificObserver",
    "MirrorScientificRuntimeBinding",
    "MirrorScientificCoverage",
    "PoupiBabyScientificConsumer",
    "ScientificConsumerRuntime",
    "ScientificConsumerRuntimeRecord",
    "build_business_os_registry",
]
