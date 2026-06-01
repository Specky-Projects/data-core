"""
app/real_estate/extractor.py — Light field extractor for direct_agencies payloads.

Promotes fields already embedded in raw payloads (titles, slugs, price_text, raw_text)
into a structured_fields dict WITHOUT modifying the original raw_data.

Supports:
  apolar          — sitemap_raw_html: URL slug + <title> tag
  imobiliariapacheco — html_cards: raw_text + price_text + URL path

Fields extracted (when available):
  listing_url     str   — canonical URL of the listing
  agency          str   — agency name (normalised)
  agency_id       str   — agency slug
  listing_code    str   — internal agency code (e.g. "103804", "LAP-232", "VT-29")
  listing_type    str   — "aluguel" | "venda"
  property_type   str   — "Apartamento" | "Casa" | "Terreno" | "Loja" | ...
  title           str   — human-readable title
  price           float | None — numeric price in BRL (None when not available)
  price_raw       str   — raw price string before parsing
  city            str   — "Curitiba"
  neighborhood    str   — bairro (title-cased)
  area_m2         float | None — floor area from title tag (Apolar only)
  extraction_confidence  str  — "high" | "medium" | "low"
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Known property types — longest-match first so "sobreloja" wins over "loja"
_PROPERTY_TYPES_ORDERED = [
    ("sobreloja", "Sobreloja"),
    ("conjunto", "Conjunto Comercial"),
    ("cobertura", "Cobertura"),
    ("apartamento", "Apartamento"),
    ("sobrado", "Sobrado"),
    ("terreno", "Terreno"),
    ("predio", "Prédio"),
    ("prédio", "Prédio"),
    ("loja", "Loja"),
    ("sala", "Sala Comercial"),
    ("casa", "Casa"),
    ("galpao", "Galpão"),
    ("galpão", "Galpão"),
    ("chacara", "Chácara"),
    ("chácara", "Chácara"),
    ("studio", "Studio"),
    ("kitnet", "Kitnet"),
]

# Pacheco code-prefix → (listing_type, property_type)
_PACHECO_PREFIX_MAP: dict[str, tuple[str, str]] = {
    "VT": ("venda", "Terreno"),
    "VC": ("venda", "Casa"),
    "VAP": ("venda", "Apartamento"),
    "VPR": ("venda", "Prédio"),
    "VSB": ("venda", "Sobrado"),
    "VL": ("venda", "Loja"),
    "VSC": ("venda", "Sala Comercial"),
    "LAP": ("aluguel", "Apartamento"),
    "LC": ("aluguel", "Casa"),
    "LSC": ("aluguel", "Sala Comercial"),
    "LT": ("aluguel", "Terreno"),
    "LG": ("aluguel", "Galpão"),
}


def _slug_to_neighborhood(slug: str) -> str:
    """Convert URL slug to title-cased neighborhood name.

    'centro-civico' → 'Centro Cívico'
    'agua-verde'    → 'Água Verde'
    'sitio-cercado' → 'Sítio Cercado'
    """
    words = slug.replace("-", " ").split()
    return " ".join(w.capitalize() for w in words)


def _parse_br_price(text: str) -> float | None:
    """Parse Brazilian price string to float.

    '3.500,00'  → 3500.0
    '850.000,00' → 850000.0
    '1.750,00'  → 1750.0
    """
    m = re.search(r"([\d]{1,3}(?:\.[\d]{3})*),(\d{2})", text)
    if not m:
        # Try without thousands separator: '3500,00'
        m = re.search(r"(\d+),(\d{2})", text)
    if not m:
        return None
    integer_part = m.group(1).replace(".", "")
    decimal_part = m.group(2)
    try:
        return float(f"{integer_part}.{decimal_part}")
    except ValueError:
        return None


def _coerce_numeric_price(value: Any) -> float | None:
    if value in (None, "", 0, "0"):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        parsed = _parse_br_price(value)
        if parsed is not None:
            return parsed
        try:
            return float(value.replace(".", "").replace(",", "."))
        except ValueError:
            return None
    return None


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", []):
            return value
    return None


def _offer_price(raw_data: dict[str, Any]) -> tuple[float | None, str | None]:
    """Extract price from common JSON-LD Offer shapes."""
    offers = raw_data.get("offers") or raw_data.get("offer")
    candidates: list[Any] = []
    if isinstance(offers, dict):
        candidates.extend(
            [
                offers.get("price"),
                offers.get("lowPrice"),
                offers.get("highPrice"),
                offers.get("monthlyRentPrice"),
            ]
        )
    elif isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict):
                candidates.extend(
                    [
                        offer.get("price"),
                        offer.get("lowPrice"),
                        offer.get("highPrice"),
                        offer.get("monthlyRentPrice"),
                    ]
                )

    for candidate in candidates:
        price = _coerce_numeric_price(candidate)
        if price is not None:
            return price, str(candidate)
    return None, None


def _raw_address(raw_data: dict[str, Any]) -> dict[str, Any]:
    address = raw_data.get("address")
    if not isinstance(address, dict):
        main_entity = raw_data.get("mainEntity")
        if isinstance(main_entity, dict):
            address = main_entity.get("address")
    return address if isinstance(address, dict) else {}


def _infer_listing_type(payload: dict[str, Any], raw_data: dict[str, Any]) -> str | None:
    text = " ".join(
        str(v)
        for v in (
            payload.get("url"),
            raw_data.get("url"),
            raw_data.get("name"),
            raw_data.get("title"),
            raw_data.get("businessFunction"),
        )
        if v
    ).lower()
    offers = raw_data.get("offers") or raw_data.get("offer")
    if isinstance(offers, dict):
        text = f"{text} {offers.get('businessFunction') or ''}".lower()
    if "alugar" in text or "aluguel" in text or "loca" in text or "leaseout" in text:
        return "aluguel"
    if "comprar" in text or "venda" in text or "sell" in text:
        return "venda"
    return None


def _infer_neighborhood(text: str) -> str | None:
    patterns = [
        r"\bno\s+(.+?)\s+de\s+[\d,.]+\s*m",
        r"\bno\s+(.+?)\s+com\s+\d+",
        r"\bbairro\s+(.+?)\s+em\s+Curitiba",
        r"-\s*([^,-|]+),\s*Curitiba\s*-",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" -|,")
            if value:
                return value
    return None


def _promote_raw_data_fields(payload: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    """Promote compatible raw_data fields into missing structured fields."""
    raw_data = payload.get("raw_data")
    if not isinstance(raw_data, dict):
        return fields

    if fields.get("price") is None:
        for key in ("price", "valor_considerado", "valoraluguelliquido", "valoraluguel", "valorvenda", "preco", "valor"):
            price = _coerce_numeric_price(raw_data.get(key))
            if price is not None:
                fields["price"] = price
                fields["price_raw"] = str(raw_data.get(key))
                break
    if fields.get("price") is None:
        price, price_raw = _offer_price(raw_data)
        if price is not None:
            fields["price"] = price
            fields["price_raw"] = price_raw

    if not fields.get("title"):
        fields["title"] = _first_present(
            raw_data.get("title"),
            raw_data.get("titulo"),
            raw_data.get("name"),
            raw_data.get("nome"),
        )
    address = _raw_address(raw_data)
    if not fields.get("city"):
        fields["city"] = _first_present(
            raw_data.get("city"),
            raw_data.get("cidade"),
            address.get("addressLocality"),
            address.get("city"),
        )
    if not fields.get("neighborhood"):
        fields["neighborhood"] = _first_present(
            raw_data.get("neighborhood"),
            raw_data.get("bairro"),
            address.get("addressNeighborhood"),
            _infer_neighborhood(str(fields.get("title") or raw_data.get("name") or "")),
        )
    if not fields.get("property_type"):
        main_entity = raw_data.get("mainEntity")
        entity_type = main_entity.get("@type") if isinstance(main_entity, dict) else None
        fields["property_type"] = _first_present(
            raw_data.get("property_type"),
            raw_data.get("tipo"),
            _detect_property_type_from_text(str(fields.get("title") or "")),
            entity_type if isinstance(entity_type, str) else None,
        )
    if not fields.get("listing_code"):
        code = raw_data.get("listing_code") or raw_data.get("referencia") or raw_data.get("codigo")
        if not code:
            code_match = re.search(r"\b(\d{3,6}(?:\.\d{3})?-[A-Z]{2})\b", str(fields.get("title") or raw_data.get("name") or ""))
            code = code_match.group(1) if code_match else None
        fields["listing_code"] = str(code) if code not in (None, "") else None
    if not fields.get("listing_type"):
        transaction = str(raw_data.get("listing_type") or raw_data.get("transacao") or "").lower()
        if "loca" in transaction or "alug" in transaction:
            fields["listing_type"] = "aluguel"
        elif "vend" in transaction or "compra" in transaction:
            fields["listing_type"] = "venda"
        else:
            fields["listing_type"] = _infer_listing_type(payload, raw_data)

    return fields


def _detect_property_type_from_text(text: str) -> str | None:
    """Detect property type from a free-text string (title, slug, raw_text)."""
    lower = unicodedata.normalize("NFC", text.lower())
    for key, label in _PROPERTY_TYPES_ORDERED:
        if key in lower:
            return label
    return None


# ---------------------------------------------------------------------------
# Per-agency extractors
# ---------------------------------------------------------------------------

def _extract_apolar_sitemap(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract fields from Apolar sitemap_raw_html payload.

    Data sources (in priority):
      1. <title> tag  — richest: type, neighborhood, city, area, transaction
      2. URL path     — transaction type, neighborhood, listing_code, property_type
    """
    url = payload.get("url", "")
    html = payload.get("raw_html_snippet", "")

    # --- URL decomposition ---
    # Full URL: https://www.apolar.com.br/alugar/curitiba/pilarzinho/alugar-...-103804
    # After filtering empty strings:
    #   [0]='https:'  [1]='www.apolar.com.br'  [2]='alugar'  [3]='curitiba'
    #   [4]='pilarzinho'  [5]='alugar-residencial-apartamento-curitiba-pilarzinho-103804'
    path_parts = [p for p in url.rstrip("/").split("/") if p]
    listing_type_raw = path_parts[2] if len(path_parts) > 2 else ""
    city_slug = path_parts[3] if len(path_parts) > 3 else ""
    neighborhood_slug = path_parts[4] if len(path_parts) > 4 else ""
    slug = path_parts[5] if len(path_parts) > 5 else ""

    listing_type = "aluguel" if listing_type_raw in ("alugar", "aluguel") else ("venda" if listing_type_raw in ("comprar", "venda") else None)
    city = city_slug.capitalize() if city_slug else None
    neighborhood = _slug_to_neighborhood(neighborhood_slug) if neighborhood_slug else None

    # listing_code = last numeric token in slug (Apolar codes: 5-6 digits)
    listing_code: str | None = None
    code_m = re.search(r"-(\d{4,8})$", slug)
    if code_m:
        listing_code = code_m.group(1)

    # property_type from slug
    property_type = _detect_property_type_from_text(slug)

    # --- Title tag ---
    # "Apartamento Residencial para Locação no Pilarzinho em Curitiba, 86.13m² | Apolar"
    title: str | None = None
    area_m2: float | None = None
    title_m = re.search(r"<title>(.*?)</title>", html, re.I)
    if title_m:
        raw_title = title_m.group(1)
        # Strip encoding artefacts (Apolar uses UTF-8 but Windows terminal may mangle)
        title = raw_title.replace("| Apolar", "").strip()
        # Area from title: "86.13m²" or "86,13m²"
        area_m = re.search(r"([\d]+[.,][\d]+)\s*m", raw_title)
        if area_m:
            try:
                area_m2 = float(area_m.group(1).replace(",", "."))
            except ValueError:
                pass
        # Refine property_type from title (more reliable than slug)
        pt_from_title = _detect_property_type_from_text(raw_title)
        if pt_from_title:
            property_type = pt_from_title
        # Refine neighborhood from title: "no Pilarzinho em Curitiba"
        bairro_m = re.search(r"\bno\s+(.+?)\s+em\s+Curitiba", raw_title, re.I)
        if bairro_m:
            neighborhood = bairro_m.group(1).strip()
        # Refine city from title
        city_m = re.search(r"\bem\s+([A-Za-zÀ-ú\s]+?)(?:,|\s*\||\s*\d)", raw_title)
        if city_m:
            city = city_m.group(1).strip()

    confidence = "high" if title and listing_code and neighborhood else (
        "medium" if listing_code or neighborhood else "low"
    )

    return {
        "listing_url": url,
        "agency": "Apolar Imóveis",
        "agency_id": "apolar",
        "listing_code": listing_code,
        "listing_type": listing_type,
        "property_type": property_type,
        "title": title,
        "price": None,          # Apolar SPA — price not in HTML snippet
        "price_raw": None,
        "city": city,
        "neighborhood": neighborhood,
        "area_m2": area_m2,
        "extraction_confidence": confidence,
    }


def _extract_apolar_api(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract fields from Apolar frontend API payload.

    The public HTML is a Vue shell with title/meta only. The frontend loads
    listing details from /properties/reference/{referencia}/main; the price is
    exposed as valor_considerado (and, for rent, related aluguel fields).
    """
    url = payload.get("url", "")
    rd = payload.get("raw_data", {}) if isinstance(payload.get("raw_data"), dict) else {}

    transacao = str(rd.get("transacao") or "").lower()
    if "loca" in transacao:
        listing_type = "aluguel"
    elif "venda" in transacao:
        listing_type = "venda"
    else:
        listing_type = None

    price = rd.get("valor_considerado")
    if price is None:
        price = rd.get("valoraluguelliquido") or rd.get("valoraluguel") or rd.get("valorvenda")
    try:
        price_value = float(price) if price is not None else None
    except (TypeError, ValueError):
        price_value = None

    area = rd.get("area_total") or rd.get("area_util") or rd.get("areaterreno")
    try:
        area_m2 = float(area) if area is not None else None
    except (TypeError, ValueError):
        area_m2 = None

    title_parts = [
        rd.get("tipo"),
        "Residencial" if rd.get("finalidade") == "Residencial" else rd.get("finalidade"),
        "para Locação" if listing_type == "aluguel" else ("à Venda" if listing_type == "venda" else None),
        f"no {rd.get('bairro')}" if rd.get("bairro") else None,
        f"em {rd.get('cidade')}" if rd.get("cidade") else None,
    ]
    title = " ".join(str(p) for p in title_parts if p)

    return {
        "listing_url": url,
        "agency": "Apolar Imóveis",
        "agency_id": "apolar",
        "listing_code": str(rd.get("referencia") or rd.get("_apolar_api_reference") or "") or None,
        "listing_type": listing_type,
        "property_type": rd.get("tipo"),
        "title": title or None,
        "price": price_value,
        "price_raw": str(price) if price is not None else None,
        "city": rd.get("cidade"),
        "neighborhood": rd.get("bairro"),
        "area_m2": area_m2,
        "extraction_confidence": "high" if price_value is not None and rd.get("referencia") else "medium",
    }


def _extract_pacheco_html_cards(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract fields from Imobiliária Pacheco html_cards payload.

    Data sources:
      raw_data.raw_text  — listing code, transaction, price
      raw_data.price_text — price (more reliable)
      URL                — /comprar/ or /locacao/ → listing_type
    """
    url = payload.get("url", "")
    rd = payload.get("raw_data", {}) if isinstance(payload.get("raw_data"), dict) else {}
    raw_text = rd.get("raw_text", "")
    price_text = rd.get("price_text", "")

    # listing_type from URL
    if "/comprar/" in url:
        listing_type = "venda"
    elif "/locacao/" in url:
        listing_type = "aluguel"
    else:
        listing_type = None

    # listing_code and property_type from code prefix
    code_m = re.match(r"([A-Z]+-\d+)", raw_text.strip())
    listing_code: str | None = None
    property_type: str | None = None
    if code_m:
        listing_code = code_m.group(1)
        prefix = listing_code.split("-")[0]
        mapped = _PACHECO_PREFIX_MAP.get(prefix)
        if mapped:
            # Override listing_type if prefix is definitive (V/L prefix)
            if not listing_type:
                listing_type = mapped[0]
            property_type = mapped[1]
        else:
            # Fallback: infer from first letter
            if prefix.startswith("V"):
                listing_type = listing_type or "venda"
            elif prefix.startswith("L"):
                listing_type = listing_type or "aluguel"
            # Try to detect type from remaining letters
            suffix = prefix[1:]  # e.g. "AP", "C", "SC"
            for s, pt in [("AP", "Apartamento"), ("SC", "Sala Comercial"), ("T", "Terreno"),
                           ("C", "Casa"), ("PR", "Prédio"), ("G", "Galpão")]:
                if suffix == s:
                    property_type = pt
                    break

    # Price: try price_text first, then raw_text
    price_raw = price_text or raw_text
    price = _parse_br_price(price_text) if price_text else _parse_br_price(raw_text)

    # Build minimal title from code + type + listing_type
    title_parts = []
    if property_type:
        title_parts.append(property_type)
    if listing_code:
        title_parts.append(f"({listing_code})")
    title = " ".join(title_parts) if title_parts else None

    confidence = "high" if listing_code and property_type and price else (
        "medium" if listing_code or price else "low"
    )

    return {
        "listing_url": url,
        "agency": "Imobiliária Pacheco",
        "agency_id": "imobiliariapacheco",
        "listing_code": listing_code,
        "listing_type": listing_type,
        "property_type": property_type,
        "title": title,
        "price": price,
        "price_raw": price_raw if price else None,
        "city": "Curitiba",        # all Pacheco listings are Curitiba
        "neighborhood": None,      # not available in html_cards payload
        "area_m2": None,
        "extraction_confidence": confidence,
    }


def _extract_imobiliariamaringa_html(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract fields from Imobiliária Maringá static HTML payloads."""
    url = payload.get("url", "")
    html = payload.get("raw_html_snippet", "")
    rd = payload.get("raw_data", {}) if isinstance(payload.get("raw_data"), dict) else {}
    raw_text = " ".join(
        str(v) for v in (
            rd.get("title"),
            rd.get("price_text"),
            rd.get("raw_text"),
            html,
        ) if v
    )

    title = rd.get("title")
    if not title:
        title_m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        if title_m:
            title = re.sub(r"\s+", " ", title_m.group(1)).strip()
    if not title:
        h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        if h1_m:
            title = re.sub(r"<[^>]+>", " ", h1_m.group(1))
            title = re.sub(r"\s+", " ", title).strip()

    price_raw = rd.get("price_text")
    if not price_raw:
        price_m = re.search(r"R\$\s*[\d\.]+,\d{2}", raw_text)
        price_raw = price_m.group(0) if price_m else None
    price = _parse_br_price(price_raw or raw_text)

    listing_type = None
    lower = f"{url} {raw_text}".lower()
    if "alugar" in lower or "loca" in lower:
        listing_type = "aluguel"
    elif "comprar" in lower or "venda" in lower or "vende" in lower:
        listing_type = "venda"

    property_type = _detect_property_type_from_text(f"{title or ''} {raw_text[:500]}")
    neighborhood = None
    neigh_m = re.search(r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ\s]+),\s*Maringá\s*-\s*PR", raw_text)
    if neigh_m:
        neighborhood = neigh_m.group(1).strip()

    area_m2 = None
    area_m = re.search(r"(\d{2,5})\s*(?:m²|m2)", raw_text, re.I)
    if area_m:
        try:
            area_m2 = float(area_m.group(1))
        except ValueError:
            area_m2 = None

    confidence = "high" if title and price else ("medium" if title or price else "low")
    return {
        "listing_url": url,
        "agency": "Imobiliária Maringá",
        "agency_id": "imobiliariamaringa",
        "listing_code": None,
        "listing_type": listing_type,
        "property_type": property_type,
        "title": title,
        "price": price,
        "price_raw": price_raw,
        "city": "Maringá",
        "neighborhood": neighborhood,
        "area_m2": area_m2,
        "extraction_confidence": confidence,
    }


def _extract_generic_raw_html(payload: dict[str, Any]) -> dict[str, Any]:
    """Minimal extraction from raw_html fallback (listing pages, not individual items)."""
    url = payload.get("url", "")
    agency_id = payload.get("agency_id", "")
    agency_name = payload.get("agency", "")
    html = payload.get("raw_html_snippet", "")
    raw_data = payload.get("raw_data", {}) if isinstance(payload.get("raw_data"), dict) else {}

    text = " ".join(str(v) for v in (url, html, raw_data.get("raw_text"), raw_data.get("title")) if v)

    # Try title tag
    title: str | None = payload.get("page_title") or raw_data.get("title")
    title_m = re.search(r"<title>(.*?)</title>", html, re.I)
    if not title and title_m:
        raw = title_m.group(1).strip()
        # Filter out generic/parked/useless titles
        _generic = {
            "imóveis", "imoveis", "home", "", "imóveis - novolar", "novolar prime view - novolar",
            "pacheco",
        }
        # Also skip anything from sedo/parked domain
        if raw and raw.lower() not in _generic and "sedo" not in raw.lower() and "recursos e informações" not in raw.lower():
            title = raw

    price_raw = raw_data.get("price_text")
    if not price_raw:
        price_m = re.search(r"R\$\s*[\d\.]+,\d{2}", text)
        price_raw = price_m.group(0) if price_m else None
    price = _parse_br_price(price_raw or "") if price_raw else None

    listing_type = _infer_listing_type(payload, raw_data)
    property_type = _detect_property_type_from_text(f"{title or ''} {url}")
    city = "Curitiba" if "curitiba" in f"{title or ''} {url}".lower() else None
    neighborhood = _infer_neighborhood(title or "")
    if not neighborhood and city:
        url_match = re.search(r"/imovel/(?:alugar|comprar|venda|locacao)-[a-z-]*?([a-z-]+)-curitiba", url)
        if url_match:
            neighborhood = _slug_to_neighborhood(url_match.group(1))

    return {
        "listing_url": url,
        "agency": agency_name,
        "agency_id": agency_id,
        "listing_code": None,
        "listing_type": listing_type,
        "property_type": property_type,
        "title": title,
        "price": price,
        "price_raw": price_raw,
        "city": city,
        "neighborhood": neighborhood,
        "area_m2": None,
        "extraction_confidence": "medium" if price and title else "low",
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def extract_structured_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Top-level dispatcher: return structured_fields dict for any direct_agencies payload.

    Does NOT modify the input payload.
    """
    agency_id = payload.get("agency_id", "")
    strategy = payload.get("strategy", "")

    if agency_id == "apolar" and strategy == "sitemap_api":
        fields = _extract_apolar_api(payload)
    elif agency_id == "apolar" and strategy == "sitemap_raw_html":
        fields = _extract_apolar_sitemap(payload)
    elif agency_id == "imobiliariapacheco" and strategy == "html_cards":
        fields = _extract_pacheco_html_cards(payload)
    elif agency_id == "imobiliariamaringa" and strategy in {
        "html_cards",
        "linked_raw_html",
        "linked_json_ld",
        "raw_html",
        "sitemap_raw_html",
    }:
        fields = _extract_imobiliariamaringa_html(payload)
    else:
        fields = _extract_generic_raw_html(payload)

    fields = _promote_raw_data_fields(payload, fields)
    previous = payload.get("structured_fields")
    if isinstance(previous, dict):
        for key, value in previous.items():
            if fields.get(key) in (None, "", []):
                fields[key] = value
    return fields


# ---------------------------------------------------------------------------
# Completeness scoring (used by enrichment job)
# ---------------------------------------------------------------------------

_COMPLETENESS_FIELDS = ["listing_url", "title", "listing_type", "property_type",
                        "price", "city", "neighborhood"]


def completeness_score(sf: dict[str, Any]) -> float:
    """Return completeness fraction (0.0–1.0) for a structured_fields dict."""
    present = sum(1 for f in _COMPLETENESS_FIELDS if sf.get(f) not in (None, "", []))
    return present / len(_COMPLETENESS_FIELDS)
