from app.modules.real_estate.collectors.base_real_estate_collector import BaseRealEstateCollector
from app.modules.real_estate.parsers.apolar_parser import ApolarParser
from app.modules.real_estate.parsers.generic_parser import GenericRealEstateParser


class ApolarCollector(BaseRealEstateCollector):
    source_name = "apolar"
    base_url = "https://www.apolar.com.br"
    city = "Curitiba"
    state = "PR"
    max_pages = 2
    max_listing_urls = 25

    def build_parser(self) -> GenericRealEstateParser:
        return ApolarParser()

    async def discover_urls(self) -> list[str]:
        seed_urls = self.config.get("seed_urls") or [
            self.url("/comprar"),
            self.url("/alugar"),
        ]
        return await self.discover_from_pages(seed_urls)

