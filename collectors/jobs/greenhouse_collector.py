"""
GreenhouseCollector — coleta vagas de emprego de empresas que usam Greenhouse.

Greenhouse oferece uma API pública por empresa sem autenticação.
Endpoint: GET https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true

Usa uma seed list de empresas brasileiras de tecnologia conhecidas no Greenhouse.
Para cada empresa, coleta todas as vagas disponíveis.

Campos coletados: id, título, empresa, localização, departamento, escritório,
descrição (HTML), data atualização, url, raw_json completo.

Salva em raw_collections (module=jobs, schema=jobPosting v1.0.0).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from collectors.base import BaseCollector, CollectedItem, CollectorMetadata
from database.models import CollectorDomain

logger = logging.getLogger(__name__)

_GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
_DEFAULT_TIMEOUT = 20.0

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Seed list: empresas brasileiras e internacionais com escritórios BR usando Greenhouse
# Formato: (slug_greenhouse, nome_display)
_SEED_COMPANIES: list[tuple[str, str]] = [
    # Fintechs & Pagamentos
    ("nubank", "Nubank"),
    ("stone-pagamentos", "Stone"),
    ("pismo", "Pismo"),
    ("dock", "Dock"),
    ("ebanx", "EBANX"),
    # Tech & E-commerce
    ("vtex", "VTEX"),
    ("quinto-andar", "QuintoAndar"),
    ("loft-co", "Loft"),
    ("gympass", "Gympass"),
    ("totvs", "TOTVS"),
    # Delivery & Logística
    ("loggi", "Loggi"),
    ("vex", "VEX"),
    # Saúde & EdTech
    ("alice", "Alice Saúde"),
    ("arco-educacao", "Arco Educação"),
    # Internacionais com escritório BR
    ("cloudflare", "Cloudflare"),
    ("datadog", "Datadog"),
    ("twilio", "Twilio"),
    ("stripe", "Stripe"),
    ("segment", "Segment"),
    ("brex", "Brex"),
]


def _extract_job(raw: dict[str, Any], company_name: str) -> dict[str, Any]:
    """Normalize a Greenhouse job dict."""
    location = raw.get("location", {}) or {}
    departments = raw.get("departments", []) or []
    offices = raw.get("offices", []) or []

    dept_names = [d.get("name") for d in departments if d.get("name")]
    office_names = [o.get("name") for o in offices if o.get("name")]

    return {
        "id": raw.get("id"),
        "title": raw.get("title"),
        "company_name": company_name,
        "location": location.get("name"),
        "departments": dept_names,
        "offices": office_names,
        "employment_type": raw.get("employment_type"),
        "updated_at": raw.get("updated_at"),
        "published_at": raw.get("published_at") or raw.get("updated_at"),
        "url": raw.get("absolute_url"),
        "internal_job_id": raw.get("internal_job_id"),
        "requisition_id": raw.get("requisition_id"),
        "description_html": raw.get("content"),
        "source": "greenhouse",
        "raw_job": {k: v for k, v in raw.items() if k != "content"},
    }


class GreenhouseCollector(BaseCollector):
    metadata = CollectorMetadata(
        name="jobs.greenhouse",
        domain=CollectorDomain.jobs,
        source="greenhouse",
        description=(
            "Coleta vagas de emprego via API pública do Greenhouse. "
            "Seed list de empresas brasileiras de tecnologia. "
            "Raw storage only."
        ),
        default_interval_minutes=360,  # 6h
        collector_version="1.0.0",
        raw_schema_name="jobPosting",
        raw_schema_version="1.0.0",
        schedulable=True,
    )

    async def collect(self) -> list[CollectedItem]:
        companies: list[tuple[str, str]] = self.config.get("companies", _SEED_COMPANIES)
        items: list[CollectedItem] = []

        async with httpx.AsyncClient(
            headers=_HEADERS,
            timeout=httpx.Timeout(_DEFAULT_TIMEOUT),
            follow_redirects=True,
        ) as client:
            for slug, display_name in companies:
                url = _GREENHOUSE_API.format(company=slug)
                try:
                    resp = await client.get(url, params={"content": "true"})
                    if resp.status_code == 404:
                        logger.debug(
                            "Greenhouse company not found",
                            extra={"company": slug},
                        )
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as exc:
                    logger.warning(
                        "Greenhouse fetch failed",
                        extra={"company": slug, "error": str(exc)},
                    )
                    continue

                jobs = data.get("jobs", []) if isinstance(data, dict) else data
                if not jobs:
                    logger.debug(
                        "Greenhouse no jobs",
                        extra={"company": slug},
                    )
                    continue

                for raw in jobs:
                    try:
                        payload = _extract_job(raw, display_name)
                        job_id = payload.get("id")
                        if not job_id:
                            continue
                        items.append(
                            CollectedItem(
                                external_id=f"GH-{job_id}",
                                source_url=payload.get("url"),
                                payload=payload,
                                metadata={
                                    "company_slug": slug,
                                    "company_name": display_name,
                                    "source": "greenhouse",
                                },
                            )
                        )
                    except Exception as exc:
                        logger.debug(
                            "Greenhouse parse error",
                            extra={"company": slug, "error": str(exc)},
                        )

                logger.info(
                    "Greenhouse company collected",
                    extra={"company": slug, "count": len(jobs)},
                )
                await asyncio.sleep(0.3)

        logger.info("Greenhouse collection complete", extra={"total_items": len(items)})
        return items
