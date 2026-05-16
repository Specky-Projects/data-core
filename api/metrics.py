"""Custom Prometheus metrics for data-core.

All counters and histograms are module-level singletons — import from here
to avoid re-registration errors when the module is imported multiple times.

Metric groups
─────────────
• price_feed_*          Legacy price-feed endpoint counters (ecommerce)
• pipeline_*            Per-stage timing and volume (collection / normalization / analytics)
• collection_*          Per-domain / per-source collection counters
• job_dead_letters_*    Scheduler dead-letter tracking
• circuit_breaker_*     Circuit-breaker state
• db_pool_*             PostgreSQL connection pool utilisation
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Summary

# ──────────────────────────────────────────────────────────────────────────────
# Legacy price-feed metrics (ecommerce)
# ──────────────────────────────────────────────────────────────────────────────

price_feed_requests_total = Counter(
    "price_feed_requests_total",
    "Total number of /price-feed requests",
    ["cursor_used"],  # 'yes' | 'no'
)

price_feed_items_served_total = Counter(
    "price_feed_items_served_total",
    "Total number of price-feed items returned to consumers",
    ["store_name"],
)

price_feed_response_size = Histogram(
    "price_feed_response_size_items",
    "Distribution of item counts returned per price-feed request",
    buckets=[0, 1, 10, 50, 100, 200, 500, 1000],
)

# ──────────────────────────────────────────────────────────────────────────────
# Pipeline stage metrics  (collection → normalization → analytics)
# ──────────────────────────────────────────────────────────────────────────────

# Labels: domain (crypto | ecommerce | real_estate | sports_betting | trading)
#         stage  (collection | normalization | analytics)
#         status (success | error)

pipeline_stage_runs_total = Counter(
    "pipeline_stage_runs_total",
    "Total number of pipeline stage executions",
    ["domain", "stage", "status"],
)

pipeline_stage_duration_seconds = Histogram(
    "pipeline_stage_duration_seconds",
    "Wall-clock duration of a single pipeline stage execution",
    ["domain", "stage"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300],
)

pipeline_items_processed_total = Counter(
    "pipeline_items_processed_total",
    "Total number of items processed per stage",
    ["domain", "stage"],
)

pipeline_items_error_total = Counter(
    "pipeline_items_error_total",
    "Total number of items that caused processing errors per stage",
    ["domain", "stage"],
)

# Active (in-flight) stage executions
pipeline_stage_active = Gauge(
    "pipeline_stage_active",
    "Number of currently executing pipeline stages",
    ["domain", "stage"],
)

# Last successful run timestamp (Unix epoch) – useful for staleness alerts
pipeline_stage_last_success_timestamp = Gauge(
    "pipeline_stage_last_success_timestamp_seconds",
    "Unix timestamp of the last successful pipeline stage completion",
    ["domain", "stage"],
)

# ──────────────────────────────────────────────────────────────────────────────
# Collection-specific metrics
# ──────────────────────────────────────────────────────────────────────────────

collection_raw_saved_total = Counter(
    "collection_raw_saved_total",
    "Total number of raw records saved per collector",
    ["domain", "collector_name"],
)

collection_raw_duplicates_total = Counter(
    "collection_raw_duplicates_total",
    "Total number of duplicate raw records skipped",
    ["domain", "collector_name"],
)

collection_errors_total = Counter(
    "collection_errors_total",
    "Total number of collection errors per collector",
    ["domain", "collector_name", "error_type"],
)

collection_duration_seconds = Histogram(
    "collection_duration_seconds",
    "Wall-clock duration of a collector run",
    ["domain", "collector_name"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600],
)

# ──────────────────────────────────────────────────────────────────────────────
# Dead-letter + scheduler
# ──────────────────────────────────────────────────────────────────────────────

job_dead_letters_total = Counter(
    "job_dead_letters_total",
    "Total number of scheduler jobs that exhausted retries and wrote a dead letter",
    ["job_name"],
)


def _unresolved_job_dead_letter_count() -> int:
    from database.models import CollectorError
    from database.session import SessionLocal

    db = SessionLocal()
    try:
        return (
            db.query(CollectorError)
            .filter(
                CollectorError.error_type == "JobDeadLetter",
                CollectorError.resolved_at.is_(None),
            )
            .count()
        )
    except Exception:
        return 0
    finally:
        db.close()


job_dead_letters_unresolved = Gauge(
    "job_dead_letters_unresolved",
    "Current number of unresolved scheduler JobDeadLetter records",
)
job_dead_letters_unresolved.set_function(_unresolved_job_dead_letter_count)

# ──────────────────────────────────────────────────────────────────────────────
# Circuit breaker
# ──────────────────────────────────────────────────────────────────────────────

circuit_breaker_opens_total = Counter(
    "circuit_breaker_opens_total",
    "Total number of times a source circuit was opened",
    ["module", "source_name"],
)


def _open_circuit_count() -> int:
    from database.models import CollectorError
    from database.session import SessionLocal

    db = SessionLocal()
    try:
        return (
            db.query(CollectorError)
            .filter(
                CollectorError.error_type == "CircuitOpen",
                CollectorError.resolved_at.is_(None),
            )
            .count()
        )
    except Exception:
        return 0
    finally:
        db.close()


circuit_breaker_open_sources = Gauge(
    "circuit_breaker_open_sources",
    "Current number of sources with an open circuit breaker",
)
circuit_breaker_open_sources.set_function(_open_circuit_count)

# ──────────────────────────────────────────────────────────────────────────────
# Database pool
# ──────────────────────────────────────────────────────────────────────────────


def _db_pool_size() -> int:
    try:
        from database.session import engine
        pool = engine.pool
        return pool.size()  # type: ignore[attr-defined]
    except Exception:
        return 0


def _db_pool_checked_out() -> int:
    try:
        from database.session import engine
        pool = engine.pool
        return pool.checkedout()  # type: ignore[attr-defined]
    except Exception:
        return 0


db_pool_size = Gauge("db_pool_size", "SQLAlchemy connection pool size")
db_pool_size.set_function(_db_pool_size)

db_pool_checked_out = Gauge(
    "db_pool_checked_out",
    "Number of connections currently checked out from the pool",
)
db_pool_checked_out.set_function(_db_pool_checked_out)


# ──────────────────────────────────────────────────────────────────────────────
# Helper: context manager for pipeline stage instrumentation
# ──────────────────────────────────────────────────────────────────────────────

import time
from contextlib import contextmanager
from typing import Generator


@contextmanager
def measure_pipeline_stage(domain: str, stage: str) -> Generator[None, None, None]:
    """Context manager that records duration, status and item-active gauge.

    Usage::

        with measure_pipeline_stage("crypto", "analytics"):
            processor.run(limit=100)
    """
    pipeline_stage_active.labels(domain=domain, stage=stage).inc()
    start = time.perf_counter()
    status = "success"
    try:
        yield
    except Exception:
        status = "error"
        pipeline_stage_runs_total.labels(domain=domain, stage=stage, status="error").inc()
        raise
    else:
        pipeline_stage_runs_total.labels(domain=domain, stage=stage, status="success").inc()
        pipeline_stage_last_success_timestamp.labels(domain=domain, stage=stage).set(time.time())
    finally:
        elapsed = time.perf_counter() - start
        pipeline_stage_duration_seconds.labels(domain=domain, stage=stage).observe(elapsed)
        pipeline_stage_active.labels(domain=domain, stage=stage).dec()
