"""
GupyCollector — coleta vagas de emprego da Gupy via API pública.

A Gupy é a maior plataforma de recrutamento do Brasil.
Usa a API pública de vagas sem autenticação (mesma usada pelo portal gupy.io).

Endpoint: GET https://portal.api.gupy.io/api/job
Paginação: offset + limit

Campos coletados: id, cargo, empresa, cidade, estado, tipo, modalidade,
data publicação, url, descrição, raw_json completo.

Salva em raw_collections (module=jobs, schema=jobPosting v1.0.0).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from collectors.base import BaseCollector, CollectedItem, CollectorMetadata
from database.models import CollectorDomain

logger = logging.getLogger(__name__)

_GUPY_API = "https://portal.api.gupy.io/api/job"
_PAGE_SIZE = 10          # Gupy API hard-caps responses at 10 items regardless of limit
_DEFAULT_MAX_PAGES = 40  # 400 vagas por termo de busca (10 × 40 pages)

# Gupy exige parâmetro `name` (termo de busca) — sem ele retorna HTTP 400.
# Usamos um conjunto de termos amplos que cobrem categorias principais do
# mercado brasileiro. O dedup por checksum evita duplicatas entre termos.
_SEARCH_TERMS = [
    "engenheiro",
    "desenvolvedor",
    "analista",
    "gerente",
    "coordenador",
    "especialista",
    "arquiteto",
    "cientista",
    "designer",
    "product manager",
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://portal.gupy.io/",
}


def _extract_job(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Gupy job dict into our standard schema.

    NOTE: As of 2026-05 the Gupy public portal API returns an empty `company`
    dict. Company name must be read from `careerPageName` instead.
    """
    company = raw.get("company", {}) or {}
    # Prefer company.name → careerPageName → jobBoard (legacy fallback)
    company_name = (
        company.get("name")
        or raw.get("careerPageName")
        or (raw.get("jobBoard", {}).get("name") if isinstance(raw.get("jobBoard"), dict) else raw.get("jobBoard"))
    )
    return {
        "id": raw.get("id"),
        "title": raw.get("name"),
        "company_name": company_name,
        "company_id": company.get("id"),
        "city": raw.get("city"),
        "state": raw.get("state"),
        "country": raw.get("country", "Brasil"),
        "workplace_type": raw.get("workplaceType"),  # on-site | remote | hybrid
        "employment_type": raw.get("type"),          # full-time | part-time | etc.
        "seniority": raw.get("educationalLevelName"),
        "department": raw.get("departmentName"),
        "published_at": raw.get("publishedDate"),
        "deadline": raw.get("applicationDeadline"),
        "url": raw.get("jobUrl") or raw.get("publicUrl"),
        "compensation": raw.get("salaryRange"),
        "source": "gupy",
        "raw_job": raw,
    }


class GupyCollector(BaseCollector):
    metadata = CollectorMetadata(
        name="jobs.gupy",
        domain=CollectorDomain.jobs,
        source="gupy",
        description=(
            "Coleta vagas de emprego da Gupy via API pública. "
            "Cobre vagas no Brasil — todas as empresas cadastradas. "
            "Raw storage only."
        ),
        default_interval_minutes=240,  # 4h
        collector_version="1.0.0",
        raw_schema_name="jobPosting",
        raw_schema_version="1.0.0",
        schedulable=True,
    )

    async def collect(self) -> list[CollectedItem]:
        max_pages: int = int(self.config.get("max_pages", _DEFAULT_MAX_PAGES))
        search_terms: list[str] = self.config.get("search_terms", _SEARCH_TERMS)
        items: list[CollectedItem] = []
        seen_ids: set[str] = set()  # dedup in-memory across search terms

        async with httpx.AsyncClient(
            headers=_HEADERS,
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        ) as client:
            for term in search_terms:
                for page in range(max_pages):
                    offset = page * _PAGE_SIZE
                    # Gupy requires `name` param — returns HTTP 400 without it
                    params = {"name": term, "offset": offset, "limit": _PAGE_SIZE}

                    try:
                        resp = await client.get(_GUPY_API, params=params)
                        resp.raise_for_status()
                        data = resp.json()
                    except Exception as exc:
                        logger.warning(
                            "Gupy API fetch failed",
                            extra={"term": term, "page": page, "offset": offset, "error": str(exc)},
                        )
                        break

                    jobs = data if isinstance(data, list) else data.get("data", [])
                    if not jobs:
                        break

                    for raw in jobs:
                        try:
                            payload = _extract_job(raw)
                            job_id = payload.get("id")
                            if not job_id:
                                continue
                            ext_id = f"GUPY-{job_id}"
                            if ext_id in seen_ids:
                                continue  # já coletado nesta run
                            seen_ids.add(ext_id)
                            items.append(
                                CollectedItem(
                                    external_id=ext_id,
                                    source_url=payload.get("url"),
                                    payload=payload,
                                    metadata={
                                        "search_term": term,
                                        "page": page,
                                        "offset": offset,
                                        "source": "gupy",
                                    },
                                )
                            )
                        except Exception as exc:
                            logger.debug("Gupy parse error", extra={"error": str(exc)})

                    pagination = data.get("pagination", {}) if isinstance(data, dict) else {}
                    # The API caps each page at _PAGE_SIZE (10). Use pagination.total
                    # to decide whether to continue rather than trusting len(jobs).
                    api_total = pagination.get("total") or 0
                    total = api_total or (len(jobs) + offset)
                    logger.info(
                        "Gupy page collected",
                        extra={"term": term, "page": page, "offset": offset,
                               "count": len(jobs), "total": total},
                    )

                    # Stop if fewer items returned than page size (genuine last page)
                    # OR if we've already fetched all available items for this term
                    if len(jobs) < _PAGE_SIZE or (api_total and offset + len(jobs) >= api_total):
                        break

                    await asyncio.sleep(0.5)

        logger.info("Gupy collection complete", extra={"total_items": len(items), "unique": len(seen_ids)})
        return items
