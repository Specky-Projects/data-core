import json
import re
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class ParsedRealEstateListing:
    external_id: str | None
    url: str
    title: str | None
    price: float | None
    property_type: str | None
    purpose: str | None
    city: str | None
    neighborhood: str | None
    address: str | None
    bedrooms: int | None
    bathrooms: int | None
    parking_spaces: int | None
    area_m2: int | None
    condo_fee: float | None
    iptu: float | None
    metadata: dict[str, Any]


class GenericRealEstateParser:
    listing_path_markers = (
        "imovel",
        "imoveis",
        "apartamento",
        "casa",
        "sobrado",
        "terreno",
        "cobertura",
        "loft",
        "studio",
        "comercial",
        "aluguel",
        "venda",
    )

    def extract_listing_links(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        for anchor in soup.select("a[href]"):
            href = anchor.get("href")
            if not href:
                continue
            url = self._absolute_url(href, base_url)
            if self.looks_like_listing_url(url):
                links.append(url)
        return sorted(set(links))

    def extract_next_page_links(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        for anchor in soup.select("a[href]"):
            label = " ".join(anchor.get_text(" ", strip=True).lower().split())
            rel = " ".join(anchor.get("rel", [])).lower() if anchor.get("rel") else ""
            href = anchor.get("href")
            if not href:
                continue
            if label in {"proxima", "próxima", "next", ">", "»"} or "next" in rel:
                links.append(self._absolute_url(href, base_url))
        return sorted(set(links))

    def looks_like_listing_url(self, url: str) -> bool:
        lower = url.lower()
        if any(marker in lower for marker in self.listing_path_markers):
            return True
        return bool(re.search(r"/(ap|ca|te|lo|co)-?\d{3,}", lower))

    def parse(self, html: str, url: str) -> ParsedRealEstateListing:
        soup = BeautifulSoup(html, "html.parser")
        json_ld = self._json_ld_objects(soup)
        text = soup.get_text(" ", strip=True)

        title = self._first_present(
            self._meta(soup, "og:title"),
            self._selector_text(soup, "h1"),
            self._selector_text(soup, "[data-testid*='title' i]"),
            self._selector_text(soup, ".title"),
        )
        address = self._first_present(
            self._meta(soup, "og:street-address"),
            self._selector_text(soup, "[class*='address' i]"),
            self._selector_text(soup, "[data-testid*='address' i]"),
        )
        price = self._extract_money(text, labels=("r$", "valor", "preço", "preco"))
        condo_fee = self._extract_labeled_money(text, ("condomínio", "condominio", "cond."))
        iptu = self._extract_labeled_money(text, ("iptu",))

        city, neighborhood = self._extract_location(text, json_ld)

        return ParsedRealEstateListing(
            external_id=self._extract_external_id(url, soup),
            url=url,
            title=title,
            price=price,
            property_type=self._extract_property_type(text, title, url),
            purpose=self._extract_purpose(text, url),
            city=city,
            neighborhood=neighborhood,
            address=address,
            bedrooms=self._extract_count(text, ("quarto", "dormitório", "dormitorio")),
            bathrooms=self._extract_count(text, ("banheiro", "bwc")),
            parking_spaces=self._extract_count(text, ("vaga", "garagem")),
            area_m2=self._extract_area(text),
            condo_fee=condo_fee,
            iptu=iptu,
            metadata={"json_ld_count": len(json_ld)},
        )

    @staticmethod
    def _absolute_url(href: str, base_url: str) -> str:
        from urllib.parse import urljoin

        return urljoin(base_url, href).split("#", 1)[0]

    @staticmethod
    def _selector_text(soup: BeautifulSoup, selector: str) -> str | None:
        node = soup.select_one(selector)
        return node.get_text(" ", strip=True) if node else None

    @staticmethod
    def _meta(soup: BeautifulSoup, property_name: str) -> str | None:
        node = soup.find("meta", attrs={"property": property_name}) or soup.find(
            "meta", attrs={"name": property_name}
        )
        value = node.get("content") if node else None
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _first_present(*values: str | None) -> str | None:
        for value in values:
            if value and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _json_ld_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
        objects: list[dict[str, Any]] = []
        for script in soup.select("script[type='application/ld+json']"):
            raw = script.string or script.get_text()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                objects.append(parsed)
            elif isinstance(parsed, list):
                objects.extend(item for item in parsed if isinstance(item, dict))
        return objects

    @staticmethod
    def _extract_money(text: str, labels: tuple[str, ...]) -> float | None:
        pattern = r"R\$\s*([\d\.\,]+)"
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            return GenericRealEstateParser._money_to_float(matches[0])
        for label in labels:
            match = re.search(rf"{re.escape(label)}\D{{0,20}}([\d\.\,]+)", text, re.IGNORECASE)
            if match:
                return GenericRealEstateParser._money_to_float(match.group(1))
        return None

    @staticmethod
    def _extract_labeled_money(text: str, labels: tuple[str, ...]) -> float | None:
        for label in labels:
            match = re.search(rf"{re.escape(label)}\D{{0,30}}R?\$?\s*([\d\.\,]+)", text, re.IGNORECASE)
            if match:
                return GenericRealEstateParser._money_to_float(match.group(1))
        return None

    @staticmethod
    def _money_to_float(value: str) -> float | None:
        cleaned = value.strip().replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _extract_count(text: str, labels: tuple[str, ...]) -> int | None:
        for label in labels:
            match = re.search(rf"(\d+)\s+{label}", text, re.IGNORECASE)
            if match:
                return int(match.group(1))
            match = re.search(rf"{label}\D{{0,15}}(\d+)", text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    def _extract_area(text: str) -> int | None:
        match = re.search(r"(\d{2,5})\s*(m²|m2|metros)", text, re.IGNORECASE)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_purpose(text: str, url: str) -> str | None:
        lower = f"{text} {url}".lower()
        if any(word in lower for word in ("aluguel", "alugar", "locação", "locacao")):
            return "rent"
        if any(word in lower for word in ("venda", "comprar", "vende-se")):
            return "sale"
        return None

    @staticmethod
    def _extract_property_type(text: str, title: str | None, url: str) -> str | None:
        lower = f"{title or ''} {text[:1000]} {url}".lower()
        types = {
            "apartment": ("apartamento", "apto", "studio", "kitnet"),
            "house": ("casa", "sobrado"),
            "land": ("terreno", "lote"),
            "commercial": ("comercial", "sala comercial", "loja"),
            "penthouse": ("cobertura",),
        }
        for normalized, markers in types.items():
            if any(marker in lower for marker in markers):
                return normalized
        return None

    @staticmethod
    def _extract_location(text: str, json_ld: list[dict[str, Any]]) -> tuple[str | None, str | None]:
        for item in json_ld:
            address = item.get("address")
            if isinstance(address, dict):
                city = address.get("addressLocality")
                neighborhood = address.get("addressRegion") or address.get("streetAddress")
                return city, neighborhood
        match = re.search(r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ\s]+)\s*-\s*([A-Z]{2})", text)
        return (match.group(1).strip(), None) if match else (None, None)

    @staticmethod
    def _extract_external_id(url: str, soup: BeautifulSoup) -> str | None:
        canonical = soup.find("link", rel="canonical")
        canonical_url = canonical.get("href") if canonical else None
        target = canonical_url or url
        match = re.search(r"(\d{4,})", target)
        return match.group(1) if match else target.rstrip("/").rsplit("/", 1)[-1]

