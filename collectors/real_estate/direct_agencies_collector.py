"""
DirectAgenciesCollector — coleta anúncios de imóveis diretamente de sites de
imobiliárias regionais (Curitiba/PR), sem depender de portais bloqueados por
Cloudflare (Zap, VivaReal, OLX, ImovelWeb).

Estratégia em cascata por site (ordem de tentativa):
  1. sitemap.xml → URLs de imóveis → fetch individual → JSON-LD
  2. Página de listagem → JSON-LD
  3. Página de listagem → __NEXT_DATA__ (Next.js)
  4. Página de listagem → cards HTML (BeautifulSoup)
  5. Fallback: raw HTML da página de listagem (garante ao menos 1 registro/site)

Salva em raw_collections:
  module=real_estate
  source_name=direct_agencies
  raw_schema_name=propertyListingRaw
  raw_schema_version=1.0.0

Cada CollectedItem.payload contém:
  - url: URL de origem
  - agency: nome da agência
  - strategy: estratégia que gerou o dado
  - raw_data: dict extraído (JSON-LD, Next.js, HTML) OU raw_html (fallback)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from collectors.base import BaseCollector, CollectedItem, CollectorMetadata
from database.models import CollectorDomain

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração das agências alvo — Curitiba/PR
# Cada entrada: (agency_id, agency_name, listing_url, sitemap_url_or_None)
# ---------------------------------------------------------------------------
_AGENCIES: list[dict[str, Any]] = [
    {
        "id": "apolar",
        "name": "Apolar Imóveis",
        "listing_urls": [],  # SPA — listing page empty; rely on sitemap only
        "sitemap": "https://www.apolar.com.br/sitemap.xml",
        # Actual URL format: /alugar/curitiba/<bairro>/<slug>-<codigo>
        "item_url_pattern": r"/(?:alugar|comprar)/curitiba/[^/]+/[a-z].*-\d+$",
    },
    # ── REMOVIDAS — audit 2026-05-30 ─────────────────────────────────────────
    # novolar: SPA sem links /imovel/; empresa de BH (não Curitiba); sem dados úteis
    # bairro: bairro.com.br é domínio parqueado com anti-bot (data-adblockkey);
    #         36 registros coletados são páginas de anti-bot, NÃO imóveis reais
    # ─────────────────────────────────────────────────────────────────────────
    {
        "id": "avanti",
        "name": "Avanti Imóveis",
        "listing_urls": [
            "https://www.avantiimoveis.com.br/imoveis/comprar/curitiba",
            "https://www.avantiimoveis.com.br/imoveis/alugar/curitiba",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "newside",
        "name": "Newside Imóveis",
        "listing_urls": [
            "https://www.newside.com.br/imoveis/venda/pr/curitiba",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "portobelo",
        "name": "Porto Belo Imóveis",
        "listing_urls": [
            "https://www.portobelo.com.br/imoveis/venda/curitiba-pr",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "globalcuritiba",
        "name": "Global Imobiliária Curitiba",
        "listing_urls": [
            "https://www.globalimobiliaria.com.br/imoveis/venda/curitiba",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "imobiliariabaldo",
        "name": "Imobiliária Baldo",
        "listing_urls": [
            "https://www.imobiliariabaldo.com.br/imoveis/venda",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "melimobiliaria",
        "name": "Mel Imobiliária",
        "listing_urls": [
            "https://www.melimobiliaria.com.br/imoveis/venda",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "patrimonioimobiliaria",
        "name": "Patrimônio Imobiliária",
        "listing_urls": [
            "https://www.patrimoniourbano.com.br/imoveis/venda/curitiba",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "imobiliariasoldado",
        "name": "Imobiliária Soldado",
        "listing_urls": [
            "https://www.imobiliariasoldado.com.br/imoveis",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "imobiliariafontana",
        "name": "Imobiliária Fontana",
        "listing_urls": [
            "https://www.imobiliariafontana.com.br/imoveis/venda",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "almarcuritiba",
        "name": "Almar Imóveis",
        "listing_urls": [
            "https://www.almar.com.br/imoveis/venda/curitiba-pr",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "inmobi",
        "name": "Inmobi Curitiba",
        "listing_urls": [
            "https://www.inmobi.com.br/imoveis/curitiba",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "chavesprimo",
        "name": "Chaves Primo",
        "listing_urls": [
            "https://www.chavesprimo.com.br/imoveis/venda/curitiba",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "ordelimoveis",
        "name": "Ordel Imóveis",
        "listing_urls": [
            "https://www.ordelimoveis.com.br/imoveis/venda/curitiba/pr",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "imobiliariagondek",
        "name": "Imobiliária Gondek",
        "listing_urls": [
            "https://www.imobiliariagondek.com.br/imoveis",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "imobiliariapacheco",
        "name": "Imobiliária Pacheco",
        "listing_urls": [
            "https://www.imobiliariapacheco.com.br/imoveis/venda",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "gruposvx",
        "name": "Grupo SVX Imóveis",
        "listing_urls": [
            "https://www.gruposvx.com.br/imoveis/venda/curitiba",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    {
        "id": "imobiliariaatp",
        "name": "Imobiliária ATP",
        "listing_urls": [
            "https://www.imobiliariaatp.com.br/imoveis/venda",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    # ── FASE 2 — Novas imobiliárias Curitiba ──────────────────────────────────
    # Prates (Casa Prates) — JSON-LD, 391 imóveis, casaprates.com.br
    {
        "id": "prates",
        "name": "Casa Prates Imóveis",
        "listing_urls": [
            "https://casaprates.com.br/imoveis",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
        # nota: pratesimoveis.com.br redireciona para casaprates.com.br
    },
    # Cibraco — JSON-LD na home, sitemap não encontrado
    {
        "id": "cibraco",
        "name": "Cibraco Imóveis",
        "listing_urls": [
            "https://cibraco.com.br/",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    # Gonzaga — HTML estático, 12 imóveis únicos por página via link-crawl
    # NOTA: www.gonzagaimoveis.com.br tem CF challenge; gonzagaimoveis.com.br (sem www) funciona
    {
        "id": "gonzaga",
        "name": "Gonzaga Imóveis",
        "listing_urls": [
            "https://gonzagaimoveis.com.br/imoveis",
            "https://gonzagaimoveis.com.br/imoveis?pagina=2",
            "https://gonzagaimoveis.com.br/imoveis?pagina=3",
            "https://gonzagaimoveis.com.br/imoveis?pagina=4",
            "https://gonzagaimoveis.com.br/imoveis?pagina=5",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/[a-z].+",
    },
    # Imobiliária Maringá — HTML indexável, sem Cloudflare/CAPTCHA observado.
    # Home e páginas /imovel/... expõem preço em texto estático.
    {
        "id": "imobiliariamaringa",
        "name": "Imobiliária Maringá",
        "listing_urls": [
            "https://imobiliariamaringa.com.br/",
            "https://imobiliariamaringa.com.br/comprar/",
            "https://imobiliariamaringa.com.br/alugar/",
        ],
        "sitemap": "https://imobiliariamaringa.com.br/sitemap.xml",
        "item_url_pattern": r"/imovel/.+",
    },
    # Cadena — JSON-LD, home tem 11 links
    {
        "id": "cadena",
        "name": "Cadena Imóveis",
        "listing_urls": [
            "https://cadenaimoveis.com.br/",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    # Noruega — JSON-LD, /imoveis 20 links
    {
        "id": "noruega",
        "name": "Imobiliária Noruega",
        "listing_urls": [
            "https://imobiliarianoruega.com.br/imoveis",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
    },
    # Razão — JSON-LD, /imoveis 37 links, 824KB
    {
        "id": "razao",
        "name": "Imobiliária Razão",
        "listing_urls": [
            "https://www.razaoimoveis.com.br/imoveis",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
        # Proven useful non-Apolar source: each page exposes 24 JSON-LD
        # listings, most with offers.price. Crawl deeper to reduce Apolar skew.
        "max_pages": 25,
    },
    # J8 (Jota8) — SPA, root 200 mas paths de listagem 404; tenta a home
    {
        "id": "j8",
        "name": "J8 Imóveis",
        "listing_urls": [
            "https://www.j8.com.br/",
        ],
        "sitemap": None,
        "item_url_pattern": r"/imovel/.+",
        # nota: j8imoveis.com.br → SSL mismatch; www.j8.com.br funciona
    },
    # ── BLOQUEADAS — documentar motivo ───────────────────────────────────────
    # tantus: DNS resolution failure (tantusimoveis.com.br não resolve)
    # bellos: Cloudflare WAF + parked domain no sedo.com
    # galvao: galvaoimoveis.com.br serve imóveis de Jundiaí/SP, não Curitiba
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    # Keep encodings to formats httpx can decode without optional brotli extras.
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

_APOLAR_API_BASE = "https://55mrb5weq7.execute-api.us-east-1.amazonaws.com/hml/properties"
_APOLAR_API_HEADERS = {
    **_HEADERS,
    "Accept": "application/json",
    "Origin": "https://www.apolar.com.br",
    "Referer": "https://www.apolar.com.br/",
}

_REALESTATE_LD_TYPES = {
    "RealEstateListing", "Residence", "House", "Apartment",
    "SingleFamilyResidence", "ApartmentComplex", "Product",
}

_DEFAULT_MAX_PAGES = 5
_MAX_SITEMAP_URLS = 400   # max property URLs to fetch from sitemap per agency
_MAX_LINKED_PAGES = 30    # max individual property pages crawled from listing-page links


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _ext_id(agency_id: str, url: str) -> str:
    h = hashlib.md5(url.encode()).hexdigest()[:12]
    return f"DIRECT-{agency_id.upper()}-{h}"


def _extract_json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Return all JSON-LD blocks of real-estate types."""
    results: list[dict[str, Any]] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") in _REALESTATE_LD_TYPES:
                    results.append(item)
        elif isinstance(data, dict):
            t = data.get("@type", "")
            if t in _REALESTATE_LD_TYPES:
                results.append(data)
            elif t == "ItemList":
                for el in data.get("itemListElement", []):
                    item = el.get("item") or el
                    if isinstance(item, dict) and item.get("@type") in _REALESTATE_LD_TYPES:
                        results.append(item)
            # Some sites wrap listings under @graph
            for node in data.get("@graph", []):
                if isinstance(node, dict) and node.get("@type") in _REALESTATE_LD_TYPES:
                    results.append(node)
    return results


def _extract_next_data(soup: BeautifulSoup) -> dict[str, Any] | None:
    """Extract __NEXT_DATA__ JSON from Next.js pages."""
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag:
        return None
    try:
        return json.loads(tag.string or "")
    except (json.JSONDecodeError, TypeError):
        return None


def _extract_html_cards(soup: BeautifulSoup, base_url: str) -> list[dict[str, Any]]:
    """Generic HTML card extractor — looks for common listing patterns."""
    results: list[dict[str, Any]] = []
    # Common selectors used across Brazilian real-estate sites
    # More specific first, generic fallback last
    card_selectors = [
        # Site-specific known-working
        ("div.item_imovel", "codigo_imovel"),   # Pacheco / imobiliariapacheco.com.br
        # Generic patterns
        ("[data-cy='property-card']", None),
        (".property-card", None),
        (".listing-card", None),
        (".imovel-card", None),
        (".card-imovel", None),
        ("article[class*='imovel']", None),
        ("article[class*='listing']", None),
        ("article[class*='property']", None),
        (".item-property", None),
        (".result-item", None),
        ("[class*='CardListing']", None),
        ("[class*='PropertyCard']", None),
        ("[class*='ImovelCard']", None),
    ]
    for selector_entry in card_selectors:
        if isinstance(selector_entry, tuple):
            selector, required_child_class = selector_entry
        else:
            selector, required_child_class = selector_entry, None
        cards = soup.select(selector)
        if required_child_class:
            # Filter to cards that actually contain the required child class
            cards = [c for c in cards if c.find(class_=required_child_class)]
        if cards:
            for card in cards:
                title_tag = card.find(["h2", "h3", "h4", "strong"])
                price_tag = card.find(attrs={"class": re.compile(r"price|preco|valor", re.I)})
                link_tag = card.find("a", href=True)
                raw_text = card.get_text(" ", strip=True)[:500]
                href = link_tag["href"] if link_tag else ""
                if href and not href.startswith("http"):
                    href = urljoin(base_url, href)
                results.append({
                    "title": title_tag.get_text(strip=True) if title_tag else None,
                    "price_text": price_tag.get_text(strip=True) if price_tag else None,
                    "url": href,
                    "raw_text": raw_text,
                })
            break  # use first selector that matched
    return results


def _extract_property_links(soup: BeautifulSoup, base_url: str, item_pattern: str) -> list[str]:
    """Extract individual property page URLs from a listing page.

    Looks for <a href="/imovel/..."> or <a href="https://..."> links whose
    path matches item_pattern. Returns deduplicated absolute URLs.
    """
    from urllib.parse import urljoin, urlparse as _urlparse
    seen: set[str] = set()
    results: list[str] = []
    base_origin = f"{_urlparse(base_url).scheme}://{_urlparse(base_url).netloc}"
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript"):
            continue
        # Make absolute
        if href.startswith("/"):
            href = base_origin + href
        elif not href.startswith("http"):
            href = urljoin(base_url, href)
        # Match against item_pattern on path only
        path = _urlparse(href).path
        if re.search(item_pattern, path) and href not in seen:
            seen.add(href)
            results.append(href)
    return results


def _parse_sitemap(content: str, domain: str, item_pattern: str) -> list[str]:
    """Extract property URLs from sitemap XML matching item_pattern."""
    urls: list[str] = []
    try:
        root = ET.fromstring(content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        # Handle sitemap index (list of sitemaps)
        for loc in root.findall(".//sm:loc", ns):
            url = (loc.text or "").strip()
            if re.search(item_pattern, url):
                urls.append(url)
    except ET.ParseError:
        # Try regex fallback
        urls = re.findall(r'<loc>(https?://[^<]+)</loc>', content)
        urls = [u for u in urls if re.search(item_pattern, u)]
    return urls[:_MAX_SITEMAP_URLS]


def _extract_apolar_reference(url: str) -> str | None:
    match = re.search(r"-(\d{4,8})/?$", url)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class DirectAgenciesCollector(BaseCollector):
    metadata = CollectorMetadata(
        name="real_estate.direct_agencies",
        domain=CollectorDomain.real_estate,
        source="direct_agencies",
        description=(
            "Coleta anúncios de imobiliárias diretas (Curitiba/PR) sem depender "
            "de portais com Cloudflare. Estratégia em cascata: "
            "sitemap → JSON-LD → __NEXT_DATA__ → HTML cards → raw HTML. "
            "Raw storage only."
        ),
        default_interval_minutes=480,  # 8h
        collector_version="1.0.0",
        raw_schema_name="propertyListingRaw",
        raw_schema_version="1.0.0",
        schedulable=True,
    )

    async def collect(self) -> list[CollectedItem]:
        max_pages: int = int(self.config.get("max_pages", _DEFAULT_MAX_PAGES))
        agencies: list[dict] = self.config.get("agencies", _AGENCIES)
        items: list[CollectedItem] = []
        seen_ids: set[str] = set()

        async with httpx.AsyncClient(
            headers=_HEADERS,
            timeout=httpx.Timeout(20.0),
            follow_redirects=True,
        ) as client:
            for agency in agencies:
                agency_id = agency["id"]
                agency_name = agency["name"]
                agency_max_pages = int(agency.get("max_pages") or max_pages)
                agency_items = await self._collect_agency(
                    client=client,
                    agency=agency,
                    max_pages=agency_max_pages,
                    seen_ids=seen_ids,
                )
                items.extend(agency_items)
                logger.info(
                    "DirectAgencies agency collected",
                    extra={
                        "agency": agency_id,
                        "agency_name": agency_name,
                        "count": len(agency_items),
                        "total_so_far": len(items),
                    },
                )
                await asyncio.sleep(1.0)  # polite inter-agency delay

        logger.info(
            "DirectAgencies collection complete",
            extra={"total_items": len(items), "unique": len(seen_ids)},
        )
        return items

    async def _collect_agency(
        self,
        client: httpx.AsyncClient,
        agency: dict[str, Any],
        max_pages: int,
        seen_ids: set[str],
    ) -> list[CollectedItem]:
        """Collect listings from one agency using cascade strategy."""
        agency_id = agency["id"]
        agency_name = agency["name"]
        item_pattern = agency.get("item_url_pattern", r"/imovel/.+")
        results: list[CollectedItem] = []

        # ----------------------------------------------------------------
        # Strategy 1: Sitemap → individual property pages → JSON-LD
        # ----------------------------------------------------------------
        sitemap_url = agency.get("sitemap")
        if sitemap_url:
            sitemap_items = await self._try_sitemap(
                client, agency_id, agency_name, sitemap_url, item_pattern, seen_ids
            )
            if sitemap_items:
                results.extend(sitemap_items)
                return results  # sitemap worked — skip listing pages

        # ----------------------------------------------------------------
        # Strategy 2-5: Listing pages (JSON-LD → Next.js → HTML → linked → raw)
        # ----------------------------------------------------------------
        for listing_url in agency.get("listing_urls", []):
            listing_items = await self._try_listing_pages(
                client, agency_id, agency_name, listing_url, max_pages, seen_ids,
                item_pattern=item_pattern,
            )
            results.extend(listing_items)
            await asyncio.sleep(0.5)

        return results

    async def _try_sitemap(
        self,
        client: httpx.AsyncClient,
        agency_id: str,
        agency_name: str,
        sitemap_url: str,
        item_pattern: str,
        seen_ids: set[str],
    ) -> list[CollectedItem]:
        """Fetch sitemap, extract property URLs, fetch each → JSON-LD."""
        try:
            resp = await client.get(sitemap_url, headers={"Accept": "application/xml,text/xml,*/*"})
            if resp.status_code != 200:
                return []
            property_urls = _parse_sitemap(resp.text, sitemap_url, item_pattern)
            if not property_urls:
                return []

            logger.info(
                "DirectAgencies sitemap found",
                extra={"agency": agency_id, "property_urls": len(property_urls)},
            )

            items: list[CollectedItem] = []
            for prop_url in property_urls:
                ext_id = _ext_id(agency_id, prop_url)
                if ext_id in seen_ids:
                    continue
                try:
                    if agency_id == "apolar":
                        api_payload = await self._try_apolar_api(client, prop_url)
                        if api_payload:
                            seen_ids.add(ext_id)
                            items.append(CollectedItem(
                                external_id=ext_id,
                                source_url=prop_url,
                                payload={
                                    "url": prop_url,
                                    "agency": agency_name,
                                    "agency_id": agency_id,
                                    "strategy": "sitemap_api",
                                    "raw_data": api_payload,
                                },
                                metadata={"agency": agency_id, "strategy": "sitemap_api"},
                            ))
                            await asyncio.sleep(0.3)
                            continue

                    prop_resp = await client.get(prop_url)
                    if prop_resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(prop_resp.text, "html.parser")
                    ld_items = _extract_json_ld(soup)
                    if ld_items:
                        for ld in ld_items:
                            seen_ids.add(ext_id)
                            items.append(CollectedItem(
                                external_id=ext_id,
                                source_url=prop_url,
                                payload={
                                    "url": prop_url,
                                    "agency": agency_name,
                                    "agency_id": agency_id,
                                    "strategy": "sitemap_json_ld",
                                    "raw_data": ld,
                                },
                                metadata={"agency": agency_id, "strategy": "sitemap_json_ld"},
                            ))
                            break  # one item per URL
                    else:
                        # Fallback: save page existence
                        seen_ids.add(ext_id)
                        items.append(CollectedItem(
                            external_id=ext_id,
                            source_url=prop_url,
                            payload={
                                "url": prop_url,
                                "agency": agency_name,
                                "agency_id": agency_id,
                                "strategy": "sitemap_raw_html",
                                "raw_html_snippet": prop_resp.text[:2000],
                            },
                            metadata={"agency": agency_id, "strategy": "sitemap_raw_html"},
                        ))
                    await asyncio.sleep(0.3)
                except Exception as exc:
                    logger.debug(
                        "DirectAgencies sitemap URL fetch error",
                        extra={"agency": agency_id, "url": prop_url, "error": str(exc)},
                    )
            return items
        except Exception as exc:
            logger.warning(
                "DirectAgencies sitemap fetch failed",
                extra={"agency": agency_id, "sitemap": sitemap_url, "error": str(exc)},
            )
            return []

    async def _try_apolar_api(
        self,
        client: httpx.AsyncClient,
        prop_url: str,
    ) -> dict[str, Any] | None:
        """Fetch Apolar structured listing data used by the Vue frontend."""
        reference = _extract_apolar_reference(prop_url)
        if not reference:
            return None
        api_url = f"{_APOLAR_API_BASE}/reference/{reference}/main"
        try:
            resp = await client.get(api_url, headers=_APOLAR_API_HEADERS)
            if resp.status_code != 200:
                logger.debug(
                    "Apolar API non-200",
                    extra={"url": prop_url, "reference": reference, "status": resp.status_code},
                )
                return None
            data = resp.json()
        except Exception as exc:
            logger.debug(
                "Apolar API fetch failed",
                extra={"url": prop_url, "reference": reference, "error": str(exc)},
            )
            return None
        if not isinstance(data, dict) or data.get("success") is not True:
            return None
        payload = data.get("data")
        if not isinstance(payload, dict):
            return None
        payload["_apolar_api_reference"] = reference
        payload["_apolar_api_url"] = api_url
        return payload

    async def _crawl_property_links(
        self,
        client: httpx.AsyncClient,
        agency_id: str,
        agency_name: str,
        prop_urls: list[str],
        seen_ids: set[str],
    ) -> list[CollectedItem]:
        """Fetch individual property pages found via link extraction.

        For each URL: try JSON-LD first, fall back to raw HTML snippet.
        Caps at _MAX_LINKED_PAGES to avoid runaway crawls.
        """
        items: list[CollectedItem] = []
        for prop_url in prop_urls[:_MAX_LINKED_PAGES]:
            ext_id = _ext_id(agency_id, prop_url)
            if ext_id in seen_ids:
                continue
            try:
                r = await client.get(prop_url)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                ld_items = _extract_json_ld(soup)
                seen_ids.add(ext_id)
                if ld_items:
                    items.append(CollectedItem(
                        external_id=ext_id,
                        source_url=prop_url,
                        payload={
                            "url": prop_url,
                            "agency": agency_name,
                            "agency_id": agency_id,
                            "strategy": "linked_json_ld",
                            "raw_data": ld_items[0],
                        },
                        metadata={"agency": agency_id, "strategy": "linked_json_ld"},
                    ))
                else:
                    items.append(CollectedItem(
                        external_id=ext_id,
                        source_url=prop_url,
                        payload={
                            "url": prop_url,
                            "agency": agency_name,
                            "agency_id": agency_id,
                            "strategy": "linked_raw_html",
                            "raw_html_snippet": r.text[:3000],
                            "page_title": soup.title.string if soup.title else None,
                        },
                        metadata={"agency": agency_id, "strategy": "linked_raw_html"},
                    ))
                await asyncio.sleep(0.4)
            except Exception as exc:
                logger.debug(
                    "DirectAgencies linked-page fetch error",
                    extra={"agency": agency_id, "url": prop_url, "error": str(exc)},
                )
        return items

    async def _try_listing_pages(
        self,
        client: httpx.AsyncClient,
        agency_id: str,
        agency_name: str,
        listing_url: str,
        max_pages: int,
        seen_ids: set[str],
        item_pattern: str = r"/imovel/.+",
    ) -> list[CollectedItem]:
        """Multi-strategy fetch of a listing/search page (paginated)."""
        items: list[CollectedItem] = []
        base_domain = f"{urlparse(listing_url).scheme}://{urlparse(listing_url).netloc}"

        for page in range(1, max_pages + 1):
            if page == 1:
                page_url = listing_url
            elif "pagina=" in urlparse(listing_url).query:
                break
            else:
                separator = "&" if urlparse(listing_url).query else "?"
                page_url = f"{listing_url}{separator}page={page}"
            try:
                resp = await client.get(page_url)
            except Exception as exc:
                logger.warning(
                    "DirectAgencies listing fetch failed",
                    extra={"agency": agency_id, "url": page_url, "error": str(exc)},
                )
                break

            # Guard: skip binary / non-HTML responses — they produce null bytes in JSONB
            content_type = resp.headers.get("content-type", "")
            if resp.status_code == 200 and not any(
                ct in content_type for ct in ("text/html", "text/plain", "application/xhtml")
            ):
                logger.debug(
                    "DirectAgencies skipping non-HTML response",
                    extra={"agency": agency_id, "url": page_url, "content_type": content_type},
                )
                break

            if resp.status_code == 404:
                break
            if resp.status_code != 200:
                logger.warning(
                    "DirectAgencies listing non-200",
                    extra={"agency": agency_id, "url": page_url, "status": resp.status_code},
                )
                # Still save raw as evidence (strategy=error_raw)
                ext_id = _ext_id(agency_id, page_url)
                if ext_id not in seen_ids:
                    seen_ids.add(ext_id)
                    items.append(CollectedItem(
                        external_id=ext_id,
                        source_url=page_url,
                        payload={
                            "url": page_url,
                            "agency": agency_name,
                            "agency_id": agency_id,
                            "strategy": "error_raw",
                            "http_status": resp.status_code,
                            "raw_html_snippet": resp.text[:1000],
                        },
                        metadata={
                            "agency": agency_id,
                            "strategy": "error_raw",
                            "http_status": resp.status_code,
                        },
                    ))
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            page_items_found = 0

            # Strategy 2: JSON-LD
            ld_listings = _extract_json_ld(soup)
            if ld_listings:
                for ld in ld_listings:
                    item_url = ld.get("url") or ld.get("@id") or page_url
                    ext_id = _ext_id(agency_id, str(item_url))
                    if ext_id in seen_ids:
                        continue
                    seen_ids.add(ext_id)
                    items.append(CollectedItem(
                        external_id=ext_id,
                        source_url=item_url,
                        payload={
                            "url": item_url,
                            "agency": agency_name,
                            "agency_id": agency_id,
                            "strategy": "json_ld",
                            "raw_data": ld,
                        },
                        metadata={"agency": agency_id, "strategy": "json_ld", "page": page},
                    ))
                    page_items_found += 1
                if page_items_found:
                    logger.debug(
                        "DirectAgencies JSON-LD hit",
                        extra={"agency": agency_id, "page": page, "count": page_items_found},
                    )

            # Strategy 3: __NEXT_DATA__
            if not page_items_found:
                next_data = _extract_next_data(soup)
                if next_data:
                    ext_id = _ext_id(agency_id, page_url + f"#nextdata-p{page}")
                    if ext_id not in seen_ids:
                        seen_ids.add(ext_id)
                        items.append(CollectedItem(
                            external_id=ext_id,
                            source_url=page_url,
                            payload={
                                "url": page_url,
                                "agency": agency_name,
                                "agency_id": agency_id,
                                "strategy": "next_data",
                                "raw_data": next_data,
                            },
                            metadata={"agency": agency_id, "strategy": "next_data", "page": page},
                        ))
                        page_items_found += 1

            # Strategy 4: HTML cards
            if not page_items_found:
                html_cards = _extract_html_cards(soup, base_domain)
                for card in html_cards:
                    card_url = card.get("url") or page_url
                    ext_id = _ext_id(agency_id, card_url)
                    if ext_id in seen_ids:
                        continue
                    seen_ids.add(ext_id)
                    items.append(CollectedItem(
                        external_id=ext_id,
                        source_url=card_url,
                        payload={
                            "url": card_url,
                            "agency": agency_name,
                            "agency_id": agency_id,
                            "strategy": "html_cards",
                            "raw_data": card,
                        },
                        metadata={"agency": agency_id, "strategy": "html_cards", "page": page},
                    ))
                    page_items_found += 1

            # Strategy 4.5: property link crawl
            # When no cards matched, check for <a href="/imovel/..."> links and
            # fetch each individual page (JSON-LD or raw HTML).
            if not page_items_found:
                prop_links = _extract_property_links(soup, page_url, item_pattern)
                if prop_links:
                    linked_items = await self._crawl_property_links(
                        client, agency_id, agency_name, prop_links, seen_ids
                    )
                    items.extend(linked_items)
                    page_items_found += len(linked_items)
                    if linked_items:
                        logger.info(
                            "DirectAgencies link-crawl hit",
                            extra={
                                "agency": agency_id,
                                "page": page,
                                "links_found": len(prop_links),
                                "items_saved": len(linked_items),
                            },
                        )

            # Strategy 5: raw HTML fallback (always saves at least 1 per page)
            if not page_items_found:
                ext_id = _ext_id(agency_id, page_url + f"#raw-p{page}")
                if ext_id not in seen_ids:
                    seen_ids.add(ext_id)
                    items.append(CollectedItem(
                        external_id=ext_id,
                        source_url=page_url,
                        payload={
                            "url": page_url,
                            "agency": agency_name,
                            "agency_id": agency_id,
                            "strategy": "raw_html",
                            "raw_html_snippet": resp.text[:3000],
                            "page_title": soup.title.string if soup.title else None,
                        },
                        metadata={"agency": agency_id, "strategy": "raw_html", "page": page},
                    ))
                    page_items_found += 1

            logger.info(
                "DirectAgencies listing page",
                extra={
                    "agency": agency_id,
                    "page": page,
                    "url": page_url,
                    "found": page_items_found,
                },
            )

            if page_items_found == 0:
                break  # no content — stop paginating

            await asyncio.sleep(1.0)

        return items
