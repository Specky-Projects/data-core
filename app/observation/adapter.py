"""ObservationAdapter — bridges legacy producers to ObservationContract.

All adapters are pure functions. No legacy objects are modified.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.observation.contract import (
    ObservationContract,
    ObservationQuality,
    ObservationType,
    stable_hash,
)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ── SIP SignalEvent adapter ────────────────────────────────────────────────────


def from_signal_event(event: dict[str, Any]) -> ObservationContract:
    """Adapt a SIP/Trading SignalEvent TypedDict to ObservationContract.

    SignalEvent shape (expected fields):
        signal_id, strategy, symbol, side, confidence, timestamp, ...
    """
    payload = {k: v for k, v in event.items() if k != "signal_id"}
    return ObservationContract.create(
        observation_id=str(event.get("signal_id", stable_hash(event, 16))),
        producer=f"sip/{event.get('strategy', 'unknown')}",
        observed_at=str(event.get("timestamp", _now_iso())),
        observation_type=ObservationType.SIGNAL,
        payload=payload,
        quality=ObservationQuality.VERIFIED,
        symbol=str(event.get("symbol", "")),
        metadata={"source": "trading.signal_event"},
    )


# ── Generic dict adapter ───────────────────────────────────────────────────────


def from_raw_dict(
    observation_id: str,
    producer: str,
    observed_at: str,
    observation_type: ObservationType,
    payload: dict[str, Any],
    symbol: str | None = None,
    quality: ObservationQuality = ObservationQuality.RAW,
    metadata: dict[str, Any] | None = None,
) -> ObservationContract:
    return ObservationContract.create(
        observation_id=observation_id,
        producer=producer,
        observed_at=observed_at,
        observation_type=observation_type,
        payload=payload,
        quality=quality,
        symbol=symbol,
        metadata=metadata or {},
    )


# ── WhaleFi funding/OI adapter ────────────────────────────────────────────────


def from_funding_rate(
    symbol: str,
    funding_rate: float,
    observed_at: str,
    exchange: str,
    extra: dict[str, Any] | None = None,
) -> ObservationContract:
    payload: dict[str, Any] = {
        "symbol": symbol,
        "funding_rate": funding_rate,
        "exchange": exchange,
        **(extra or {}),
    }
    return ObservationContract.create(
        observation_id=stable_hash({"symbol": symbol, "observed_at": observed_at, "exchange": exchange}, 20),
        producer=f"whalefi/{exchange}",
        observed_at=observed_at,
        observation_type=ObservationType.FUNDING,
        payload=payload,
        quality=ObservationQuality.VERIFIED,
        symbol=symbol,
        metadata={"exchange": exchange},
    )


def from_open_interest(
    symbol: str,
    open_interest: float,
    observed_at: str,
    exchange: str,
    extra: dict[str, Any] | None = None,
) -> ObservationContract:
    payload: dict[str, Any] = {
        "symbol": symbol,
        "open_interest": open_interest,
        "exchange": exchange,
        **(extra or {}),
    }
    return ObservationContract.create(
        observation_id=stable_hash({"symbol": symbol, "observed_at": observed_at, "oi": True, "exchange": exchange}, 20),
        producer=f"whalefi/{exchange}",
        observed_at=observed_at,
        observation_type=ObservationType.OPEN_INTEREST,
        payload=payload,
        quality=ObservationQuality.VERIFIED,
        symbol=symbol,
        metadata={"exchange": exchange},
    )
