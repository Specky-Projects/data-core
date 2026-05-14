from app.modules.sports_odds.collectors.base_sports_odds_collector import (
    BaseSportsOddsCollector,
    OddsCollectionTarget,
)
from app.modules.sports_odds.parsers import GenericOddsParser, NbaOddsParser


class NbaOddsCollector(BaseSportsOddsCollector):
    sportsbook_name = "nba_odds_example"
    base_url = "https://example.com"
    sport = "basketball"
    league_name = "NBA"
    max_events = 25

    def build_parser(self) -> GenericOddsParser:
        return NbaOddsParser()

    async def discover_events(self) -> list[OddsCollectionTarget]:
        endpoints = self.config.get("api_endpoints") or self.config.get("seed_urls") or []
        return [
            OddsCollectionTarget(endpoint=endpoint if endpoint.startswith("http") else self.url(endpoint))
            for endpoint in endpoints
        ]
