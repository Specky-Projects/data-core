from collectors.base import BaseCollector, CollectedItem, CollectorMetadata
from database.models import CollectorDomain


class GenericProductCollector(BaseCollector):
    metadata = CollectorMetadata(
        name="ecommerce.generic_product",
        domain=CollectorDomain.ecommerce,
        source="generic_marketplace",
        description="Placeholder ecommerce collector — retorna produto demo hardcoded. NÃO usar em produção.",
        default_interval_minutes=60,
        raw_schema_name="genericProduct",
        raw_schema_version="1.0.0",
        schedulable=False,  # MOCK_ONLY — dado hardcoded, não agendável
    )

    async def collect(self) -> list[CollectedItem]:
        return [
            CollectedItem(
                external_id="demo-product-1",
                source_url="https://example.com/products/demo-product-1",
                payload={
                    "sku": "demo-product-1",
                    "name": "Demo product",
                    "price": 129.9,
                    "currency": "BRL",
                    "availability": "in_stock",
                },
            )
        ]
