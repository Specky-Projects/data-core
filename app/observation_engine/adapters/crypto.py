"""Crypto adapter — synthetic stub."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.observation_engine.contracts import (
    ObservationHealth,
    ObservationRecord,
    ObservationSeverity,
)
from app.scientific_identity.contract import stable_hash


class CryptoAdapter:
    adapter_name = "crypto"
    project = "poupi-crypto"
    domain = "CRYPTO"

    def collect(self) -> list[ObservationRecord]:
        ts = datetime.utcnow()
        return [
            ObservationRecord(
                observation_id=stable_hash({"source": "crypto-binance", "ts": ts.isoformat()}),
                scientific_id=stable_hash({"producer": self.adapter_name, "ts": ts.isoformat()}),
                lineage_id=str(uuid4()),
                project=self.project,
                domain=self.domain,
                source="binance",
                severity=ObservationSeverity.INFO,
                health=ObservationHealth.HEALTHY,
                evidence=[],
                metrics={"open_orders": 0, "positions": 1, "equity_usdt": 92.92},
                timestamp=ts,
            )
        ]

    def health(self) -> dict:
        return {"status": "HEALTHY", "adapter": self.adapter_name}
