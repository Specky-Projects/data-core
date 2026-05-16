"""Correlation ID / Trace ID middleware for data-core.

Every HTTP request receives two identifiers that travel through the entire
request lifetime and are injected into every log record emitted during that
request:

• X-Correlation-ID  — supplied by the caller (or generated if absent).
                      Useful for end-to-end tracing across multiple services.
• X-Trace-ID        — always generated server-side (UUID4).
                      Identifies this specific request within data-core.

The IDs are stored in Python contextvars so that any log record emitted from
any module during the request automatically includes them via the
``CorrelationFilter`` installed by ``logs/config.py``.

Both IDs are echoed back to the caller in the response headers.

Usage (app/main.py)::

    from app.middleware.correlation import CorrelationMiddleware
    app.add_middleware(CorrelationMiddleware)
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# ── Context variables ─────────────────────────────────────────────────────────
# These are set per-request and read by CorrelationFilter in logs/config.py.

_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")
_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


def get_correlation_id() -> str:
    return _correlation_id_var.get()


def get_trace_id() -> str:
    return _trace_id_var.get()


# ── Middleware ────────────────────────────────────────────────────────────────


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Injects correlation_id and trace_id into context vars and response headers."""

    CORRELATION_HEADER = "X-Correlation-ID"
    TRACE_HEADER = "X-Trace-ID"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Honour caller-supplied correlation id; generate one if absent
        correlation_id = request.headers.get(self.CORRELATION_HEADER) or str(uuid.uuid4())
        trace_id = str(uuid.uuid4())

        token_corr = _correlation_id_var.set(correlation_id)
        token_trace = _trace_id_var.set(trace_id)
        try:
            response = await call_next(request)
        finally:
            _correlation_id_var.reset(token_corr)
            _trace_id_var.reset(token_trace)

        response.headers[self.CORRELATION_HEADER] = correlation_id
        response.headers[self.TRACE_HEADER] = trace_id
        return response
