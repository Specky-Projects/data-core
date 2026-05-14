from urllib.parse import urlparse

from app.modules.sports_odds.collectors.base_sports_odds_collector import (
    BaseSportsOddsCollector,
    OddsCollectionTarget,
)


class GenericOddsCollector(BaseSportsOddsCollector):
    sportsbook_name = "generic_sportsbook"
    base_url = "https://example.com"

    def __init__(self, *args, domain: str | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if domain:
            parsed = urlparse(domain if domain.startswith(("http://", "https://")) else f"https://{domain}")
            self.base_url = f"{parsed.scheme}://{parsed.netloc}"
            self.sportsbook_name = parsed.netloc.replace("www.", "")

    async def discover_events(self) -> list[OddsCollectionTarget]:
        endpoints = self.config.get("api_endpoints") or self.config.get("seed_urls") or [self.base_url]
        render_js = bool(self.config.get("render_js", False))
        return [
            OddsCollectionTarget(endpoint=endpoint if endpoint.startswith("http") else self.url(endpoint), render_js=render_js)
            for endpoint in endpoints
        ]
