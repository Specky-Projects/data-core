from app.analytics.models import TradingAnalytics
from app.analytics.services import BaseAnalyticsProcessor
from app.normalization.models import NormalizedMarketCandle


class TradingAnalyticsProcessor(BaseAnalyticsProcessor):
    module = "trading"

    def load_normalized(self, *, limit: int = 100) -> list[NormalizedMarketCandle]:
        return (
            self.db.query(NormalizedMarketCandle)
            .filter(NormalizedMarketCandle.analytics_status == "pending")
            .order_by(NormalizedMarketCandle.timestamp)
            .limit(limit)
            .all()
        )

    def calculate(self, normalized: NormalizedMarketCandle) -> dict:
        return {
            "symbol": normalized.symbol,
            "timeframe": normalized.timeframe,
            "rsi": None,
            "moving_average_fast": None,
            "moving_average_slow": None,
            "atr": None,
            "trend_score": None,
        }

    def save_analytics(self, normalized: NormalizedMarketCandle, analytics: object | None) -> int:
        if not isinstance(analytics, dict):
            return 0
        self.db.add(
            TradingAnalytics(
                source_normalizer_name=normalized.normalizer_name,
                source_normalizer_version=normalized.normalizer_version,
                **analytics,
            )
        )
        self.db.flush()
        return 1
