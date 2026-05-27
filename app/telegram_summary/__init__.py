"""Telegram Longitudinal Summary — automated deterministic summaries via Telegram Bot API.

Sends three types of scheduled summaries (NO LLM, NO AI, pure aggregations):
  • Operational (hourly)   : runtime health, dataset status, replayability, scores
  • Quant (6h)             : win rate, expectancy, PF, risk level, BOOST status
  • Longitudinal (daily)   : 24h vs 7d comparison of quant performance

Plus immediate alert summaries for critical state changes (with cooldown):
  • safe_mode activation, low confidence, low replayability, quant_critical

Architecture
────────────
  dto.py         — payload dataclasses (OperationalSummaryPayload, etc.)
  metrics.py     — Prometheus counters (telegram_summary_*)
  formatters/    — pure functions: payload → HTML string (≤20 lines each)
  services/      — data gathering via DB queries and aggregations
  jobs.py        — scheduler job functions (hourly, 6h, daily)

Rules (invariants — NEVER violate)
───────────────────────────────────
  NEVER use OpenAI / any LLM for content generation
  NEVER send raw logs, traces, or full JSON dumps
  NEVER send more than ~20 lines per message
  NEVER crash the scheduler on any error
  ALWAYS use deterministic aggregations only
  ALWAYS handle send failures gracefully
  ALWAYS respect cooldown before re-sending the same alert type
  ALWAYS check feature flags before sending
"""
