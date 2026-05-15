import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    delay_seconds: float = 2.0,
    label: str = "sports_odds_operation",
) -> T:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError, ValueError) as exc:
            last_error = exc
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning(
                "Sports odds retryable failure",
                extra={
                    "label": label,
                    "attempt": attempt,
                    "attempts": attempts,
                    "status_code": status_code,
                    "error": str(exc),
                },
            )
            if status_code and status_code not in {408, 425, 429, 500, 502, 503, 504}:
                raise
            if attempt < attempts:
                await asyncio.sleep(delay_seconds * attempt)
    if last_error:
        raise last_error
    raise RuntimeError("Retry failed without an exception")
