import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from playwright.async_api import Page, async_playwright
from sqlalchemy.orm import Session

from app.raw.service import RawCollectionInput, RawService
from app.modules.sports_odds.models import SportsBook, SportsEvent, SportsRawPayload
from app.modules.sports_odds.parsers import GenericOddsParser, ParsedOddsPayload, ParsedSportsEvent
from app.modules.sports_odds.services import SportsOddsService
from app.modules.sports_odds.utils.retry import retry_async

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SportsOddsCollectorResult:
    sportsbook_name: str
    discovered_events: int
    collected_events: int
    collected_odds: int
    errors: int
    elapsed_seconds: float


@dataclass(frozen=True)
class OddsCollectionTarget:
    endpoint: str
    render_js: bool = False


class BaseSportsOddsCollector(ABC):
    sportsbook_name: str
    base_url: str
    sport: str = "basketball"
    league_name: str = "NBA"
    max_events: int = 50
    timeout_seconds: float = 30.0
    timeout_ms: int = 30_000
    headless: bool = True
    collector_version: str = "1.0.0"
    raw_schema_name: str = "sportsOddsSnapshot"
    raw_schema_version: str = "1.0.0"
    parser: GenericOddsParser

    def __init__(self, db: Session, *, config: dict | None = None) -> None:
        self.db = db
        self.config = config or {}
        self.service = SportsOddsService(db)
        self.raw_service = RawService(db)
        self.parser = self.build_parser()
        self.max_events = int(self.config.get("max_events", self.max_events))
        self.headless = bool(self.config.get("headless", self.headless))

    def build_parser(self) -> GenericOddsParser:
        return GenericOddsParser()

    @abstractmethod
    async def discover_events(self) -> list[OddsCollectionTarget]:
        """Discover API endpoints or pages that contain odds for events."""

    async def collect_odds(self, target: OddsCollectionTarget) -> str:
        if target.render_js:
            return await retry_async(
                lambda: self.fetch_rendered_payload(target.endpoint),
                attempts=3,
                delay_seconds=2,
                label=f"render_odds:{target.endpoint}",
            )
        return await retry_async(
            lambda: self.fetch_api_payload(target.endpoint),
            attempts=3,
            delay_seconds=2,
            label=f"fetch_odds:{target.endpoint}",
        )

    def parse_odds(self, payload: str, target: OddsCollectionTarget) -> ParsedOddsPayload:
        return self.parser.parse(payload, endpoint=target.endpoint, sportsbook_name=self.sportsbook_name)

    def save_raw(self, *, sportsbook: SportsBook, target: OddsCollectionTarget, payload: str) -> SportsRawPayload:
        if target.render_js:
            self.raw_service.save_html(
                module="sports_odds",
                source_name=sportsbook.name,
                collector_name=self.__class__.__name__,
                collector_version=self.collector_version,
                raw_schema_name="sportsOddsHtmlPage",
                raw_schema_version=self.raw_schema_version,
                source_id=str(sportsbook.id),
                target_url=target.endpoint,
                endpoint=target.endpoint,
                response_status=200,
                raw_content=payload,
                metadata={
                    "sport": self.sport,
                    "league": self.league_name,
                    "render_js": target.render_js,
                },
            )
        else:
            self.raw_service.save_json(
                module="sports_odds",
                source_name=sportsbook.name,
                collector_name=self.__class__.__name__,
                collector_version=self.collector_version,
                raw_schema_name=self.raw_schema_name,
                raw_schema_version=self.raw_schema_version,
                source_id=str(sportsbook.id),
                endpoint=target.endpoint,
                response_status=200,
                raw_json={"payload": payload},
                metadata={
                    "sport": self.sport,
                    "league": self.league_name,
                    "render_js": target.render_js,
                },
            )
        return self.service.save_raw(sportsbook=sportsbook, endpoint=target.endpoint, payload=payload)

    def normalize(self, parsed: ParsedOddsPayload) -> ParsedOddsPayload:
        return parsed

    def save_event(self, parsed: ParsedSportsEvent) -> SportsEvent:
        return self.service.save_event(parsed)

    def save_odds_snapshot(self, *, sportsbook: SportsBook, event: SportsEvent, parsed: ParsedSportsEvent) -> int:
        saved = 0
        for market in parsed.markets:
            market_bookmaker = market.bookmaker or sportsbook.name
            bookmaker = sportsbook
            if market_bookmaker != sportsbook.name:
                bookmaker = self.service.get_or_create_sportsbook(name=market_bookmaker, base_url=self.base_url)
            self.service.save_odds_snapshot(event=event, sportsbook=bookmaker, parsed=market)
            saved += 1
        return saved

    async def run(self) -> SportsOddsCollectorResult:
        started = time.perf_counter()
        sportsbook = self.service.get_or_create_sportsbook(name=self.sportsbook_name, base_url=self.base_url)
        targets = (await self.discover_events())[: self.max_events]
        collected_events = 0
        collected_odds = 0
        errors = 0

        for target in targets:
            try:
                payload = await self.collect_odds(target)
                self.save_raw(sportsbook=sportsbook, target=target, payload=payload)
                parsed = self.normalize(self.parse_odds(payload, target))
                for event_payload in parsed.events:
                    event = self.save_event(event_payload)
                    collected_odds += self.save_odds_snapshot(
                        sportsbook=sportsbook,
                        event=event,
                        parsed=event_payload,
                    )
                    collected_events += 1
                self.db.commit()
            except Exception as exc:
                self.db.rollback()
                errors += 1
                logger.exception(
                    "Failed to collect sports odds",
                    extra={"endpoint": target.endpoint, "error": str(exc)},
                )

        elapsed = time.perf_counter() - started
        logger.info(
            "Sports odds collector finished",
            extra={
                "sportsbook": self.sportsbook_name,
                "discovered_events": len(targets),
                "collected_events": collected_events,
                "collected_odds": collected_odds,
                "errors": errors,
                "elapsed_seconds": round(elapsed, 3),
            },
        )
        return SportsOddsCollectorResult(
            sportsbook_name=self.sportsbook_name,
            discovered_events=len(targets),
            collected_events=collected_events,
            collected_odds=collected_odds,
            errors=errors,
            elapsed_seconds=elapsed,
        )

    async def fetch_api_payload(self, endpoint: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = await client.get(endpoint, headers={"accept": "application/json,text/html,*/*"})
            response.raise_for_status()
            return response.text

    async def fetch_rendered_payload(self, endpoint: str) -> str:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.headless)
            try:
                page = await browser.new_page()
                await page.goto(endpoint, wait_until="domcontentloaded", timeout=self.timeout_ms)
                await self._wait_for_render(page)
                return await page.content()
            finally:
                await browser.close()

    async def _wait_for_render(self, page: Page) -> None:
        await page.wait_for_load_state("networkidle", timeout=self.timeout_ms)

    def url(self, path: str) -> str:
        return urljoin(self.base_url, path)
