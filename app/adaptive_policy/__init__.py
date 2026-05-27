"""Adaptive Policy Contract — Phase 10.

Bridges Phase 9 Adaptive Intelligence with the Operational Enforcement layer.
Synthesises AI risk signals + Operational Truth scores into a single versioned
AdaptivePolicyContract consumed by dashboards and downstream enforcement hints.

NEVER:
  - triggers live trading automatically
  - alters signals directly
  - breaks DRY_RUN / replayability / datasets / telemetry

ALWAYS:
  - advisory-first
  - incremental (rollout phases 1-4)
  - reversible
  - observable and auditable
  - conservative: any error → OBSERVE_ONLY fallback
"""
