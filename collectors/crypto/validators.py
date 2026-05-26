"""Symbol list validation for the OHLCV collector.

Validates DEFAULT_SYMBOLS and any env-override list before attempting exchange connections.
Raises ValueError immediately on bad input so collection fails fast rather than silently
fetching partial data.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Accepted quote currencies — extend only when a new stablecoin/pair is explicitly supported.
_ACCEPTED_QUOTES: frozenset[str] = frozenset({"USDT", "USDC", "BUSD", "BTC", "ETH", "BNB"})

# Minimal symbol format: "BASE/QUOTE" — base is 2-10 uppercase alphanumeric chars.
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,10}/[A-Z0-9]{2,10}$")


def validate_symbols(symbols: list[str]) -> list[str]:
    """Validate a list of trading pair symbols.

    Checks:
    - Non-empty list
    - Each symbol matches BASE/QUOTE format
    - No duplicates
    - Quote currency is a recognised stablecoin/major

    Returns the validated list unchanged.

    Raises:
        ValueError: with a descriptive message identifying the problematic entry.
    """
    if not symbols:
        raise ValueError(
            "OHLCV collector: symbol list is empty. "
            "Set DEFAULT_SYMBOLS or the SYMBOLS env var to at least one pair (e.g. BTC/USDT)."
        )

    seen: set[str] = set()
    errors: list[str] = []

    for symbol in symbols:
        if not isinstance(symbol, str) or not symbol.strip():
            errors.append(f"  - {symbol!r}: must be a non-empty string")
            continue

        s = symbol.strip().upper()

        if not _SYMBOL_RE.match(s):
            errors.append(f"  - {symbol!r}: must be 'BASE/QUOTE' format (e.g. BTC/USDT)")
            continue

        quote = s.split("/")[1]
        if quote not in _ACCEPTED_QUOTES:
            errors.append(
                f"  - {symbol!r}: quote currency '{quote}' not in accepted set {sorted(_ACCEPTED_QUOTES)}. "
                "Add to _ACCEPTED_QUOTES in validators.py if intentional."
            )

        if s in seen:
            errors.append(f"  - {symbol!r}: duplicate symbol detected")
        seen.add(s)

    if errors:
        raise ValueError(
            "OHLCV collector: invalid symbol configuration:\n" + "\n".join(errors)
        )

    return symbols


def log_active_symbols(symbols: list[str], timeframes: list[str], extra: dict[str, Any] | None = None) -> None:
    """Emit a structured INFO log listing the symbols and timeframes that will be collected.

    Designed to be called once at the start of each collect() invocation so that every
    scheduler run has an auditable record of what was actually processed.
    """
    log_extra: dict[str, Any] = {
        "active_symbols": symbols,
        "active_timeframes": timeframes,
        "symbol_count": len(symbols),
        "timeframe_count": len(timeframes),
        "pair_combinations": len(symbols) * len(timeframes),
    }
    if extra:
        log_extra.update(extra)

    logger.info(
        "OHLCV collector: active symbol/timeframe matrix — %d symbols × %d timeframes = %d pairs",
        len(symbols),
        len(timeframes),
        len(symbols) * len(timeframes),
        extra=log_extra,
    )
