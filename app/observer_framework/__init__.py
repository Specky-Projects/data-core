"""Observer Framework — snapshot-based production observability.

Business OS 6.0 Post-Phase-2 architecture: Claude Code never connects to
production directly (no DATABASE_URL, Redis, Coolify API, Docker socket, VPS
SSH, exchange API, or token of any kind). Production access belongs
exclusively to the Business OS's own collectors (app.observation_engine's
adapters — some already real, most still synthetic stubs pending real
implementation by the Observer Framework).

The only interface between production and Claude Code is a deterministic,
serialisable ``RuntimeSnapshotContract``:

    Business OS (Observation Engine) -> RuntimeSnapshotContract (JSON)
                                              |
                                              v
                                       Claude Code (Diagnosis)
                                              |
                                              v
                              Root Cause Analysis + Recovery Plan (advisory)
                                              |
                        (Business OS's Recovery Engine executes, out of band)
                                              |
                                              v
                                  Validation Snapshot -> Claude Code
                                              |
                                              v
                                Certification + Knowledge Engine feed
"""
from __future__ import annotations

OBSERVER_FRAMEWORK_VERSION = "observer-framework-v1"
READ_ONLY = True
ADVISORY_ONLY = True
NO_DIRECT_PRODUCTION_ACCESS = True
