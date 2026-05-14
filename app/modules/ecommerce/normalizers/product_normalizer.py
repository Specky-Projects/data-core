from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
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
        if payload.get("success") is False:
            return None
        title = _clean_text(payload.get("title") or payload.get("name"))
        price = _parse_decimal(payload.get("price"))
        if not title and price is None:
            return None
        return {
            "source_id": raw.source_id,
            "external_id": payload.get("external_id") or raw.source_id or raw.target_url,
            "canonical_product_id": payload.get("canonical_product_id"),
            "title": title,
            "brand": _clean_text(payload.get("brand")),
            "price": price,
            "currency": str(payload.get("currency") or "BRL").upper(),
            "availability": str(payload.get("availability")) if payload.get("availability") is not None else None,
            "store_name": payload.get("store_name") or payload.get("store") or raw.source_name,
            "city": payload.get("city") or raw.metadata_json.get("city"),
            "state": payload.get("state") or raw.metadata_json.get("state"),
            "shipping_price": _parse_decimal(payload.get("shipping_price")),
            "collected_at": raw.collected_at or datetime.now(timezone.utc),
        }

    def normalization_metadata(self, raw: RawCollection) -> dict[str, Any]:
        metadata = super().normalization_metadata(raw)
        payload = raw.raw_json.get("scrapedProduct") if isinstance(raw.raw_json, dict) else None
        if isinstance(payload, dict):
            metadata.update(
                {
                    "raw_success": payload.get("success"),
                    "raw_error": payload.get("error"),
                    "raw_store": payload.get("store"),
                    "target_url": raw.target_url,
                }
            )
        return metadata

    def save_normalized(self, raw: RawCollection, normalized: object | list[object] | None) -> int:
        if not isinstance(normalized, dict):
            return 0
        self.db.add(NormalizedProduct(raw_collection_id=raw.id, **normalized))
        self.db.flush()
        return 1


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _parse_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("R$", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None
