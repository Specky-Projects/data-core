from collectors.base import BaseCollector, CollectedItem, CollectorMetadata
from database.models import CollectorDomain


class GenericSportsOddsCollector(BaseCollector):
    metadata = CollectorMetadata(
        name="sports_betting.generic_odds",
        domain=CollectorDomain.sports_betting,
        source="generic_bookmaker",
        description="Example sports betting collector prepared for odds payloads.",
        default_interval_minutes=15,
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
