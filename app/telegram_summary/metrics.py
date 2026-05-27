"""Prometheus metrics for the Telegram Summary layer.

All metrics use the ``telegram_summary_`` prefix.

Counters
────────
  telegram_summary_sent_total      — messages successfully delivered
  telegram_summary_failures_total  — send failures (network / API / exception)
  telegram_alert_sent_total        — immediate alert messages delivered
  telegram_rate_limited_total      — alerts suppressed by cooldown
"""

from __future__ import annotations

from prometheus_client import Counter

# ── Delivery counters ──────────────────────────────────────────────────────────

telegram_summary_sent_total = Counter(
    "telegram_summary_sent_total",
    "Number of Telegram summary messages successfully sent",
    ["summary_type"],  # operational | quant | longitudinal
)

telegram_summary_failures_total = Counter(
    "telegram_summary_failures_total",
    "Number of Telegram summary message send failures",
    ["summary_type"],  # operational | quant | longitudinal | alert
)

# ── Alert counters ─────────────────────────────────────────────────────────────

telegram_alert_sent_total = Counter(
    "telegram_alert_sent_total",
    "Number of Telegram immediate alert messages successfully sent",
    ["alert_type", "severity"],
)

telegram_rate_limited_total = Counter(
    "telegram_rate_limited_total",
    "Number of Telegram alerts suppressed by cooldown (rate limiting)",
    ["alert_type"],
)
