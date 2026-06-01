from collectors.base import BaseCollector
from collectors.crypto.crypto_coin_ohlcv import CryptoCoinOHLCVCollector
from collectors.crypto.generic_price import GenericCryptoPriceCollector
from collectors.ecommerce.generic_product import GenericProductCollector
from collectors.jobs.greenhouse_collector import GreenhouseCollector
from collectors.jobs.gupy_collector import GupyCollector
from collectors.real_estate.direct_agencies_collector import DirectAgenciesCollector
from collectors.real_estate.generic_listing import GenericRealEstateCollector
from collectors.sports_betting.generic_odds import GenericSportsOddsCollector

CollectorType = type[BaseCollector]


class CollectorRegistry:
    def __init__(self) -> None:
        self._collectors: dict[str, CollectorType] = {}

    def register(self, collector_type: CollectorType) -> None:
        self._collectors[collector_type.metadata.name] = collector_type

    def get(self, name: str) -> CollectorType:
        try:
            return self._collectors[name]
        except KeyError as exc:
            raise KeyError(f"Collector not registered: {name}") from exc

    def all(self) -> list[CollectorType]:
        return list(self._collectors.values())

    def names(self) -> list[str]:
        return sorted(self._collectors.keys())


registry = CollectorRegistry()

# ── Existing verticals ────────────────────────────────────────────────────────
registry.register(GenericRealEstateCollector)   # mock/demo — schedulable=False
registry.register(GenericProductCollector)
registry.register(GenericCryptoPriceCollector)
registry.register(CryptoCoinOHLCVCollector)
registry.register(GenericSportsOddsCollector)

# Server-first collection profile: only proven bounded collectors are registered
# for now. Portals/ATS integrations can be added back after individual smokes.
registry.register(DirectAgenciesCollector)
registry.register(GupyCollector)
registry.register(GreenhouseCollector)
