from sqlalchemy import desc

from app.analytics.models import SportsOddsAnalytics
from app.analytics.services import BaseAnalyticsProcessor
from app.normalization.models import NormalizedSportsOdd


class SportsOddsAnalyticsProcessor(BaseAnalyticsProcessor):
    module = "sports_odds"

    def load_normalized(self, *, limit: int = 100) -> list[NormalizedSportsOdd]:
        return (
            self.db.query(NormalizedSportsOdd)
            .filter(NormalizedSportsOdd.analytics_status == "pending")
            .order_by(NormalizedSportsOdd.collected_at)
            .limit(limit)
            .all()
        )

    def calculate(self, normalized: NormalizedSportsOdd) -> dict:
        opening = (
            self.db.query(NormalizedSportsOdd)
            .filter(
                NormalizedSportsOdd.event_external_id == normalized.event_external_id,
                NormalizedSportsOdd.market_type == normalized.market_type,
                NormalizedSportsOdd.selection == normalized.selection,
            )
            .order_by(NormalizedSportsOdd.collected_at)
            .first()
        )
        latest = (
            self.db.query(NormalizedSportsOdd)
            .filter(
                NormalizedSportsOdd.event_external_id == normalized.event_external_id,
                NormalizedSportsOdd.market_type == normalized.market_type,
                NormalizedSportsOdd.selection == normalized.selection,
            )
            .order_by(desc(NormalizedSportsOdd.collected_at))
            .first()
        )
        opening_odd = float(opening.odd) if opening and opening.odd is not None else None
        current_odd = float(latest.odd) if latest and latest.odd is not None else None
        return {
            "event_id": normalized.event_external_id,
            "market_type": normalized.market_type,
            "selection": normalized.selection,
            "opening_odd": opening_odd,
            "current_odd": current_odd,
            "closing_odd": None,
            "line_movement": current_odd - opening_odd if opening_odd is not None and current_odd is not None else None,
            "clv": None,
            "ev_estimate": None,
        }

    def save_analytics(self, normalized: NormalizedSportsOdd, analytics: object | None) -> int:
        if not isinstance(analytics, dict):
            return 0
        self.db.add(
            SportsOddsAnalytics(
                source_normalizer_name=normalized.normalizer_name,
                source_normalizer_version=normalized.normalizer_version,
                **analytics,
            )
        )
        self.db.flush()
        return 1
