import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    delay_seconds: float = 2.0,
    label: str = "real_estate_operation",
) -> T:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Real estate retryable failure",
                extra={"label": label, "attempt": attempt, "attempts": attempts, "error": str(exc)},
            )
            if attempt < attempts:
                await asyncio.sleep(delay_seconds * attempt)
    if last_error:
        raise last_error
    raise RuntimeError("Retry failed without an exception")

