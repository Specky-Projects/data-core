from collectors.base import BaseCollector, CollectedItem, CollectorMetadata
from database.models import CollectorDomain


class GenericRealEstateCollector(BaseCollector):
    metadata = CollectorMetadata(
        name="real_estate.generic_listing",
        domain=CollectorDomain.real_estate,
        source="generic_real_estate",
        description="Example real estate collector prepared for listing payloads.",
        default_interval_minutes=120,
        raw_schema_name="realEstateListing",
        raw_schema_version="1.0.0",
    )

    async def collect(self) -> list[CollectedItem]:
        return [
            CollectedItem(
                external_id="demo-listing-1",
                source_url="https://example.com/listings/demo-listing-1",
                payload={
                    "title": "Demo apartment",
                    "price": 350000,
                    "currency": "BRL",
                    "city": "Sao Paulo",
                    "bedrooms": 2,
                    "area_m2": 62,
                },
            )
        ]
