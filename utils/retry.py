import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    max_attempts: int,
    delay_seconds: int,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> T:
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await operation()
        except retry_exceptions as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
            logger.warning(
                "Retrying operation after failure",
                extra={"attempt": attempt, "max_attempts": max_attempts, "error": str(exc)},
            )
            await asyncio.sleep(delay_seconds)

    if last_error is None:
        raise RuntimeError("Retry operation failed without an exception")
    raise last_error

