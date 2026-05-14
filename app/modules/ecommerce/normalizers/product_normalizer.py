from datetime import datetime, timezone
from typing import Any

from app.normalization.models import NormalizedProduct
from app.normalization.services import BaseNormalizer
from app.raw.models import RawCollection


class EcommerceProductNormalizer(BaseNormalizer):
    module = "ecommerce"
    normalizer_name = "generic_product_normalizer"
    normalizer_version = "1.0.0"

    def normalize(self, raw: RawCollection) -> dict[str, Any] | None:
        if not isinstance(raw.raw_json, dict):
            return None
        payload = raw.raw_json.get("scrapedProduct") or raw.raw_json.get("scraped_product") or raw.raw_json
        return {
            "source_id": raw.source_id,
            "external_id": payload.get("external_id") or raw.source_id,
            "canonical_product_id": payload.get("canonical_product_id"),
            "title": payload.get("title") or payload.get("name"),
            "brand": payload.get("brand"),
            "price": payload.get("price"),
            "currency": payload.get("currency") or "BRL",
            "availability": str(payload.get("availability")) if payload.get("availability") is not None else None,
            "store_name": payload.get("store_name") or payload.get("store") or raw.source_name,
            "city": payload.get("city") or raw.metadata_json.get("city"),
            "state": payload.get("state") or raw.metadata_json.get("state"),
            "shipping_price": payload.get("shipping_price"),
            "collected_at": raw.collected_at or datetime.now(timezone.utc),
        }

    def save_normalized(self, raw: RawCollection, normalized: object | list[object] | None) -> int:
        if not isinstance(normalized, dict):
            return 0
        self.db.add(NormalizedProduct(raw_collection_id=raw.id, **normalized))
        self.db.flush()
        return 1
