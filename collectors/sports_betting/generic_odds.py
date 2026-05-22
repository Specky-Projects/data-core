from collectors.base import BaseCollector, CollectedItem, CollectorMetadata
from database.models import CollectorDomain


class GenericSportsOddsCollector(BaseCollector):
    metadata = CollectorMetadata(
        name="sports_betting.generic_odds",
        domain=CollectorDomain.sports_betting,
        source="generic_bookmaker",
        description="Placeholder odds — retorna match demo hardcoded. NÃO usar em produção.",
        default_interval_minutes=15,
        raw_schema_name="genericOddsSnapshot",
        raw_schema_version="1.0.0",
        schedulable=False,  # MOCK_ONLY — dado hardcoded, não agendável
    )

    async def collect(self) -> list[CollectedItem]:
        return [
            CollectedItem(
                external_id="demo-match-1:home_win",
                source_url="https://example.com/odds/demo-match-1",
                payload={
                    "event_id": "demo-match-1",
                    "sport": "football",
                    "market": "1x2",
                    "selection": "home_win",
                    "odd": 1.95,
                },
            )
        ]
