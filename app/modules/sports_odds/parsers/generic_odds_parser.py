import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class ParsedOddsMarket:
    market_type: str
    selection: str
    odd: float
    handicap: float | None = None
    total_points: float | None = None
    bookmaker: str | None = None


@dataclass(frozen=True)
class ParsedSportsEvent:
    external_id: str | None
    sport: str
    league_name: str
    country: str | None
    home_team: str
    away_team: str
    start_time: datetime | None
    event_status: str
    markets: list[ParsedOddsMarket] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedOddsPayload:
    events: list[ParsedSportsEvent]
    metadata: dict[str, Any] = field(default_factory=dict)


class GenericOddsParser:
    default_sport = "basketball"
    default_league = "unknown"
    default_country: str | None = None

    def parse(self, payload: str, *, endpoint: str, sportsbook_name: str) -> ParsedOddsPayload:
        stripped = payload.strip()
        if not stripped:
            return ParsedOddsPayload(events=[], metadata={"endpoint": endpoint, "empty": True})
        if stripped.startswith(("{", "[")):
            return self.parse_json(stripped, endpoint=endpoint, sportsbook_name=sportsbook_name)
        return self.parse_html(stripped, endpoint=endpoint, sportsbook_name=sportsbook_name)

    def parse_json(self, payload: str, *, endpoint: str, sportsbook_name: str) -> ParsedOddsPayload:
        data = json.loads(payload)
        event_items = self._event_items(data)
        events = [event for item in event_items if (event := self._parse_event_item(item, sportsbook_name))]
        return ParsedOddsPayload(events=events, metadata={"endpoint": endpoint, "source_format": "json"})

    def parse_html(self, payload: str, *, endpoint: str, sportsbook_name: str) -> ParsedOddsPayload:
        soup = BeautifulSoup(payload, "html.parser")
        json_events: list[ParsedSportsEvent] = []
        for script in soup.select("script[type='application/json'], script[type='application/ld+json']"):
            raw = script.string or script.get_text()
            try:
                parsed = self.parse_json(raw, endpoint=endpoint, sportsbook_name=sportsbook_name)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            json_events.extend(parsed.events)
        return ParsedOddsPayload(
            events=json_events,
            metadata={"endpoint": endpoint, "source_format": "html", "json_event_count": len(json_events)},
        )

    def _parse_event_item(self, item: dict[str, Any], sportsbook_name: str) -> ParsedSportsEvent | None:
        home_team, away_team = self._teams(item)
        if not home_team or not away_team:
            return None

        markets = self._markets(item, sportsbook_name)
        return ParsedSportsEvent(
            external_id=self._string(item, "id", "event_id", "external_id", "key", "slug"),
            sport=self._string(item, "sport", "sport_key") or self.default_sport,
            league_name=self._string(item, "league", "league_name", "competition") or self.default_league,
            country=self._string(item, "country") or self.default_country,
            home_team=home_team,
            away_team=away_team,
            start_time=self._datetime(item, "start_time", "commence_time", "event_time", "scheduled"),
            event_status=self._string(item, "status", "event_status", "state") or "scheduled",
            markets=markets,
            metadata={"raw_market_count": len(markets)},
        )

    def _markets(self, item: dict[str, Any], default_bookmaker: str) -> list[ParsedOddsMarket]:
        markets: list[ParsedOddsMarket] = []
        direct_markets = item.get("markets") if isinstance(item.get("markets"), list) else []
        markets.extend(self._parse_market_items(direct_markets, default_bookmaker))

        bookmakers = item.get("bookmakers") if isinstance(item.get("bookmakers"), list) else []
        for bookmaker in bookmakers:
            if not isinstance(bookmaker, dict):
                continue
            bookmaker_name = self._string(bookmaker, "title", "name", "key") or default_bookmaker
            nested = bookmaker.get("markets") if isinstance(bookmaker.get("markets"), list) else []
            markets.extend(self._parse_market_items(nested, bookmaker_name))
        return markets

    def _parse_market_items(self, market_items: list[Any], bookmaker_name: str) -> list[ParsedOddsMarket]:
        parsed: list[ParsedOddsMarket] = []
        for market in market_items:
            if not isinstance(market, dict):
                continue
            market_type = self._normalize_market_type(self._string(market, "key", "type", "market_type", "name"))
            outcomes = market.get("outcomes") if isinstance(market.get("outcomes"), list) else []
            for outcome in outcomes:
                if not isinstance(outcome, dict):
                    continue
                odd = self._float(outcome.get("price") or outcome.get("odd") or outcome.get("decimal"))
                selection = self._string(outcome, "name", "selection", "label", "team")
                if odd is None or not selection:
                    continue
                handicap = self._float(outcome.get("point") or outcome.get("handicap") or outcome.get("line"))
                parsed.append(
                    ParsedOddsMarket(
                        market_type=market_type,
                        selection=selection,
                        odd=odd,
                        handicap=handicap,
                        total_points=handicap if market_type == "totals" else None,
                        bookmaker=bookmaker_name,
                    )
                )
        return parsed

    def _event_items(self, data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if not isinstance(data, dict):
            return []
        for key in ("events", "data", "games", "matches"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if self._teams(data) != (None, None):
            return [data]
        return []

    @staticmethod
    def _teams(item: dict[str, Any]) -> tuple[str | None, str | None]:
        home = GenericOddsParser._string(item, "home_team", "home", "homeTeam")
        away = GenericOddsParser._string(item, "away_team", "away", "awayTeam")
        competitors = item.get("competitors") or item.get("teams")
        if (not home or not away) and isinstance(competitors, list) and len(competitors) >= 2:
            names = [GenericOddsParser._string(team, "name", "team", "displayName") for team in competitors]
            home = home or names[0]
            away = away or names[1]
        return home, away

    @staticmethod
    def _normalize_market_type(value: str | None) -> str:
        if not value:
            return "unknown"
        lower = value.lower().replace(" ", "_")
        aliases = {
            "h2h": "moneyline",
            "winner": "moneyline",
            "spreads": "spread",
            "spread": "spread",
            "totals": "totals",
            "total": "totals",
            "player_props": "player_props",
        }
        return aliases.get(lower, lower)

    @staticmethod
    def _string(item: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = item.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    @staticmethod
    def _float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _datetime(item: dict[str, Any], *keys: str) -> datetime | None:
        value = GenericOddsParser._string(item, *keys)
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
