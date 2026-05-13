from collectors.base import BaseCollector, CollectedItem, CollectorMetadata
from database.models import CollectorDomain


class GenericCryptoPriceCollector(BaseCollector):
    metadata = CollectorMetadata(
        name="crypto.generic_price",
        domain=CollectorDomain.crypto,
        source="generic_exchange",
        description="Example crypto collector prepared for market price payloads.",
        default_interval_minutes=5,
    )

    async def collect(self) -> list[CollectedItem]:
        return [
            CollectedItem(
                external_id="BTC-BRL",
                source_url="https://example.com/markets/BTC-BRL",
                payload={
                    "symbol": "BTC-BRL",
                    "last_price": 350000.0,
                    "currency": "BRL",
                    "volume_24h": 123.45,
                },
            )
        ]
