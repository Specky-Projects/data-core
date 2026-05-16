"""Centralised logging configuration for data-core.

Features
────────
• Plain-text format (default) or structured JSON (LOG_JSON=true).
• ``CorrelationFilter`` automatically injects ``correlation_id`` and
  ``trace_id`` into every log record from the active request context.
• ``PipelineFilter`` adds ``pipeline_domain`` and ``pipeline_stage`` when
  set via ``set_pipeline_context()``.
• Log level configurable via ``LOG_LEVEL`` env var (default: INFO).

JSON record fields (when LOG_JSON=true)
───────────────────────────────────────
  timestamp, level, logger, message,
  correlation_id, trace_id,
  pipeline_domain, pipeline_stage,
  + any extra={} kwargs passed to the logger call

Usage
─────
    # In scheduler jobs or workers — set pipeline context before running:
    from logs.config import set_pipeline_context, clear_pipeline_context
    set_pipeline_context(domain="crypto", stage="analytics")
    try:
        processor.run()
    finally:
        clear_pipeline_context()
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

from pythonjsonlogger import jsonlogger

from core.config import settings

# ── Pipeline context vars ─────────────────────────────────────────────────────

_pipeline_domain_var: ContextVar[str] = ContextVar("pipeline_domain", default="-")
_pipeline_stage_var: ContextVar[str] = ContextVar("pipeline_stage", default="-")


def set_pipeline_context(*, domain: str, stage: str) -> None:
    """Set the current pipeline domain/stage for structured log enrichment."""
    _pipeline_domain_var.set(domain)
    _pipeline_stage_var.set(stage)


def clear_pipeline_context() -> None:
    _pipeline_domain_var.set("-")
    _pipeline_stage_var.set("-")


# ── Log filters ───────────────────────────────────────────────────────────────


class CorrelationFilter(logging.Filter):
    """Injects correlation_id and trace_id into every log record.

    Values come from the ContextVars maintained by
    ``app.middleware.correlation``.  When called outside a request context
    (e.g. scheduler jobs) the values default to ``"-"``.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from app.middleware.correlation import get_correlation_id, get_trace_id
            record.correlation_id = get_correlation_id()
            record.trace_id = get_trace_id()
        except Exception:
            record.correlation_id = "-"
            record.trace_id = "-"
        return True


class PipelineFilter(logging.Filter):
    """Injects pipeline_domain and pipeline_stage into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.pipeline_domain = _pipeline_domain_var.get()
        record.pipeline_stage = _pipeline_stage_var.get()
        return True


# ── Public API ────────────────────────────────────────────────────────────────


def configure_logging() -> None:
    """Configure root logger.  Call once at application startup."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(CorrelationFilter())
    handler.addFilter(PipelineFilter())

    if settings.log_json:
        formatter: logging.Formatter = jsonlogger.JsonFormatter(
            fmt=(
                "%(asctime)s %(levelname)s %(name)s %(message)s "
                "%(correlation_id)s %(trace_id)s "
                "%(pipeline_domain)s %(pipeline_stage)s"
            ),
            rename_fields={
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger",
                "correlation_id": "correlation_id",
                "trace_id": "trace_id",
                "pipeline_domain": "pipeline_domain",
                "pipeline_stage": "pipeline_stage",
            },
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            " | cid=%(correlation_id)s tid=%(trace_id)s"
            " | domain=%(pipeline_domain)s stage=%(pipeline_stage)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    logging.basicConfig(level=settings.log_level.upper(), handlers=[handler], force=True)
