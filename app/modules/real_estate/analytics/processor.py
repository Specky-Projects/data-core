from app.analytics.models import RealEstateAnalytics
from app.analytics.services import BaseAnalyticsProcessor
from app.normalization.models import NormalizedRealEstateListing


class RealEstateAnalyticsProcessor(BaseAnalyticsProcessor):
    module = "real_estate"

    def load_normalized(self, *, limit: int = 100) -> list[NormalizedRealEstateListing]:
        return (
            self.db.query(NormalizedRealEstateListing)
            .filter(NormalizedRealEstateListing.analytics_status == "pending")
            .order_by(NormalizedRealEstateListing.collected_at)
            .limit(limit)
            .all()
        )

    def calculate(self, normalized: NormalizedRealEstateListing) -> dict:
        price = float(normalized.price) if normalized.price is not None else None
        area = normalized.area_m2
        price_per_m2 = price / area if price is not None and area else None
        return {
            "price_per_m2": price_per_m2,
            "neighborhood_avg_price_m2": None,
            "discount_vs_neighborhood": None,
            "opportunity_score": None,
        }

    def save_analytics(self, normalized: NormalizedRealEstateListing, analytics: object | None) -> int:
        if not isinstance(analytics, dict):
            return 0
        self.db.add(
            RealEstateAnalytics(
                listing_id=normalized.id,
                source_normalizer_name=normalized.normalizer_name,
                source_normalizer_version=normalized.normalizer_version,
                **analytics,
            )
        )
        self.db.flush()
        return 1
