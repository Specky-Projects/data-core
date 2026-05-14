import logging
from typing import Any

from collectors.base import BaseCollector, CollectedItem, CollectorMetadata
from database.models import CollectorDomain
from domains.crypto_coin.config.settings import load_config
from domains.crypto_coin.core.execution.exchange_connector import ExchangeConnector

logger = logging.getLogger(__name__)


class CryptoCoinOHLCVCollector(BaseCollector):
    metadata = CollectorMetadata(
        name="crypto.crypto_coin_ohlcv",
        domain=CollectorDomain.crypto,
        source="crypto_coin_exchange",
        description="Collects OHLCV candles through the migrated crypto-coin exchange connector.",
        default_interval_minutes=15,
        raw_schema_name="marketCandle",
        raw_schema_version="1.0.0",
    )

    async def collect(self) -> list[CollectedItem]:
        cfg = load_config(self.config.get("env_file", ".env"))
        limit = int(self.config.get("limit", 50))
        connector = ExchangeConnector(cfg, logger)

        try:
            await connector.connect()
            df = await connector.fetch_ohlcv(limit=limit)
            if df is None or df.empty:
                return []

            items: list[CollectedItem] = []
            for timestamp, row in df.tail(limit).iterrows():
                ts = timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)
                payload: dict[str, Any] = {
                    "symbol": cfg.symbol,
                    "exchange": cfg.exchange,
                    "timeframe": cfg.timeframe,
                    "timestamp": ts,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                }
                items.append(
                    CollectedItem(
                        external_id=f"{cfg.exchange}:{cfg.symbol}:{cfg.timeframe}:{ts}",
                        source_url=None,
                        payload=payload,
                        metadata={"domain_module": "domains.crypto_coin"},
                    )
                )
            return items
        finally:
            await connector.close()
