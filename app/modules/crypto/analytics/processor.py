from app.analytics.models import CryptoAnalytics
from app.analytics.services import BaseAnalyticsProcessor
from app.normalization.models import NormalizedCryptoSnapshot


class CryptoAnalyticsProcessor(BaseAnalyticsProcessor):
    module = "crypto"

    def load_normalized(self, *, limit: int = 100) -> list[NormalizedCryptoSnapshot]:
        return (
            self.db.query(NormalizedCryptoSnapshot)
            .filter(NormalizedCryptoSnapshot.analytics_status == "pending")
            .order_by(NormalizedCryptoSnapshot.collected_at)
            .limit(limit)
            .all()
        )

    def calculate(self, normalized: NormalizedCryptoSnapshot) -> dict:
        return {
            "symbol": normalized.symbol,
            "volatility_24h": None,
            "volume_spike_score": None,
            "trend_score": None,
            "regime": None,
        }

    def save_analytics(self, normalized: NormalizedCryptoSnapshot, analytics: object | None) -> int:
        if not isinstance(analytics, dict):
            return 0
        self.db.add(
            CryptoAnalytics(
                source_normalizer_name=normalized.normalizer_name,
                source_normalizer_version=normalized.normalizer_version,
                **analytics,
            )
        )
        self.db.flush()
        return 1
