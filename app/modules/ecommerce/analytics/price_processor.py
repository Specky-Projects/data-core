from app.analytics.models import ProductPriceAnalytics
from app.analytics.services import BaseAnalyticsProcessor
from app.normalization.models import NormalizedProduct


class ProductPriceAnalyticsProcessor(BaseAnalyticsProcessor):
    module = "ecommerce"

    def load_normalized(self, *, limit: int = 100) -> list[NormalizedProduct]:
        return (
            self.db.query(NormalizedProduct)
            .filter(NormalizedProduct.analytics_status == "pending")
            .order_by(NormalizedProduct.collected_at)
            .limit(limit)
            .all()
        )

    def calculate(self, normalized: NormalizedProduct) -> dict:
        price = float(normalized.price) if normalized.price is not None else None
        return {
            "avg_price_7d": price,
            "avg_price_30d": price,
            "min_price_90d": price,
            "max_price_90d": price,
            "price_score": None,
        }

    def save_analytics(self, normalized: NormalizedProduct, analytics: object | None) -> int:
        if not isinstance(analytics, dict):
            return 0
        self.db.add(
            ProductPriceAnalytics(
                product_id=normalized.id,
                source_normalizer_name=normalized.normalizer_name,
                source_normalizer_version=normalized.normalizer_version,
                **analytics,
            )
        )
        self.db.flush()
        return 1
