from urllib.parse import urlparse

from app.modules.real_estate.collectors.base_real_estate_collector import BaseRealEstateCollector


class GenericRealEstateCollector(BaseRealEstateCollector):
    source_name = "generic_real_estate"
    base_url = "https://example.com"

    def __init__(self, *args, domain: str | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if domain:
            parsed = urlparse(domain if domain.startswith(("http://", "https://")) else f"https://{domain}")
            self.base_url = f"{parsed.scheme}://{parsed.netloc}"
            self.source_name = parsed.netloc.replace("www.", "")

    async def discover_urls(self) -> list[str]:
        seed_urls = self.config.get("seed_urls") or [self.base_url]
        return await self.discover_from_pages(seed_urls)

