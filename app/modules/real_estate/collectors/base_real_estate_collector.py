import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urljoin

from playwright.async_api import Page, async_playwright
from sqlalchemy.orm import Session

from app.raw.service import RawCollectionInput, RawService
from app.modules.real_estate.models import RealEstateListing, RealEstateRawPage, RealEstateSource
from app.modules.real_estate.parsers.generic_parser import GenericRealEstateParser, ParsedRealEstateListing
from app.modules.real_estate.services import RealEstateService
from app.modules.real_estate.utils.retry import retry_async

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RealEstateCollectorResult:
    source_name: str
    discovered_urls: int
    collected_listings: int
    invalid_urls: int
    errors: int
    elapsed_seconds: float


class BaseRealEstateCollector(ABC):
    source_name: str
    base_url: str
    city: str | None = None
    state: str | None = None
    max_pages: int = 3
    max_listing_urls: int = 50
    timeout_ms: int = 30_000
    headless: bool = True
    collector_version: str = "1.0.0"
    raw_schema_name: str = "realEstateHtmlPage"
    raw_schema_version: str = "1.0.0"
    parser: GenericRealEstateParser

    def __init__(self, db: Session, *, config: dict | None = None) -> None:
        self.db = db
        self.config = config or {}
        self.service = RealEstateService(db)
        self.raw_service = RawService(db)
        self.parser = self.build_parser()
        self.max_pages = int(self.config.get("max_pages", self.max_pages))
        self.max_listing_urls = int(self.config.get("max_listing_urls", self.max_listing_urls))
        self.headless = bool(self.config.get("headless", self.headless))

    def build_parser(self) -> GenericRealEstateParser:
        return GenericRealEstateParser()

    @abstractmethod
    async def discover_urls(self) -> list[str]:
        """Discover listing URLs from search/listing pages."""

    async def collect_listing(self, url: str) -> str:
        async def _collect() -> str:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=self.headless)
                try:
                    page = await browser.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                    await self._wait_for_render(page)
                    return await page.content()
                finally:
                    await browser.close()

        return await retry_async(_collect, attempts=3, delay_seconds=2, label=f"collect_listing:{url}")

    def parse_listing(self, html: str, url: str) -> ParsedRealEstateListing:
        return self.parser.parse(html, url)

    def save_raw(
        self,
        *,
        url: str,
        html: str,
        listing: RealEstateListing | None = None,
    ) -> RealEstateRawPage:
        self.raw_service.save_html(
                module="real_estate",
                source_name=self.source_name,
                collector_name=self.__class__.__name__,
                collector_version=self.collector_version,
                raw_schema_name=self.raw_schema_name,
                raw_schema_version=self.raw_schema_version,
                source_id=str(listing.external_id) if listing and listing.external_id else None,
                target_url=url,
                response_status=200,
                raw_content=html,
                metadata={
                    "city": self.city,
                    "state": self.state,
                },
        )
        return self.service.save_raw(url=url, html=html, listing=listing)

    def normalize(self, parsed: ParsedRealEstateListing) -> ParsedRealEstateListing:
        return parsed

    def save_listing(
        self,
        *,
        source: RealEstateSource,
        parsed: ParsedRealEstateListing,
    ) -> RealEstateListing:
        return self.service.save_listing(source=source, parsed=parsed)

    def save_price_history(self, *, listing: RealEstateListing, price: float | None) -> None:
        self.service.save_price_history(listing=listing, price=price)

    async def run(self) -> RealEstateCollectorResult:
        started = time.perf_counter()
        source = self.service.get_or_create_source(
            name=self.source_name,
            base_url=self.base_url,
            city=self.city,
            state=self.state,
        )
        discovered = await self.discover_urls()
        discovered = discovered[: self.max_listing_urls]
        collected = 0
        invalid = 0
        errors = 0

        for url in discovered:
            if not self.parser.looks_like_listing_url(url):
                invalid += 1
                continue
            try:
                html = await self.collect_listing(url)
                parsed = self.normalize(self.parse_listing(html, url))
                listing = self.save_listing(source=source, parsed=parsed)
                self.save_raw(url=url, html=html, listing=listing)
                self.save_price_history(listing=listing, price=parsed.price)
                self.db.commit()
                collected += 1
            except Exception as exc:
                self.db.rollback()
                errors += 1
                logger.exception("Failed to collect real estate listing", extra={"url": url, "error": str(exc)})

        elapsed = time.perf_counter() - started
        logger.info(
            "Real estate collector finished",
            extra={
                "source": self.source_name,
                "discovered_urls": len(discovered),
                "collected_listings": collected,
                "invalid_urls": invalid,
                "errors": errors,
                "elapsed_seconds": round(elapsed, 3),
            },
        )
        return RealEstateCollectorResult(
            source_name=self.source_name,
            discovered_urls=len(discovered),
            collected_listings=collected,
            invalid_urls=invalid,
            errors=errors,
            elapsed_seconds=elapsed,
        )

    async def fetch_rendered_html(self, url: str) -> str:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.headless)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                await self._wait_for_render(page)
                return await page.content()
            finally:
                await browser.close()

    async def discover_from_pages(self, seed_urls: list[str]) -> list[str]:
        pending = list(seed_urls)
        visited: set[str] = set()
        listing_urls: set[str] = set()

        while pending and len(visited) < self.max_pages:
            url = pending.pop(0)
            if url in visited:
                continue
            visited.add(url)
            html = await retry_async(
                lambda url=url: self.fetch_rendered_html(url),
                attempts=3,
                delay_seconds=2,
                label=f"discover:{url}",
            )
            listing_urls.update(self.parser.extract_listing_links(html, url))
            for next_url in self.parser.extract_next_page_links(html, url):
                if next_url not in visited:
                    pending.append(next_url)

        return sorted(listing_urls)

    async def _wait_for_render(self, page: Page) -> None:
        await page.wait_for_load_state("networkidle", timeout=self.timeout_ms)

    def url(self, path: str) -> str:
        return urljoin(self.base_url, path)
