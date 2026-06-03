from collectors.base import BaseCollector
from collectors.crypto.crypto_coin_ohlcv import CryptoCoinOHLCVCollector
from collectors.crypto.generic_price import GenericCryptoPriceCollector
from collectors.ecommerce.generic_product import GenericProductCollector
from collectors.jobs.greenhouse_collector import GreenhouseCollector
from collectors.jobs.gupy_collector import GupyCollector
from collectors.jobs.lever_collector import LeverCollector
from collectors.jobs.recruitee_collector import RecruiteeCollector
from collectors.jobs.smartrecruiters_collector import SmartRecruitersCollector
from collectors.jobs.teamtailor_collector import TeamtailorCollector
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

registry.register(DirectAgenciesCollector)
# Jobs — ativos (auto-scheduler 6h interval cada)
registry.register(GupyCollector)
registry.register(GreenhouseCollector)
registry.register(LeverCollector)
registry.register(SmartRecruitersCollector)
registry.register(RecruiteeCollector)
registry.register(TeamtailorCollector)
# workable: REMOVIDO 2026-06-01 — 0 output em validação; slugs BR inexistentes na plataforma
