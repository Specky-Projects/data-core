import base64
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from api.deps import db_session
from api.metrics import price_feed_items_served_total, price_feed_requests_total, price_feed_response_size
from app.normalization.models import NormalizedProduct
from domains.poupi_baby.interface import get_interface_summary, list_endpoints, list_modules

router = APIRouter(prefix="/api/v1/poupi-baby", tags=["poupi-baby"])


@router.get("")
def summary() -> dict:
    return get_interface_summary()


@router.get("/modules")
def modules() -> list[dict]:
    return list_modules()


@router.get("/endpoints")
def endpoints() -> list[dict]:
    return list_endpoints()


def _encode_cursor(collected_at: datetime, row_id: uuid.UUID) -> str:
    payload = {"t": collected_at.isoformat(), "id": str(row_id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, str] | None:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(payload["t"]), str(payload["id"])
    except Exception:
        return None


@router.get("/price-feed")
def price_feed(
    db: Session = Depends(db_session),
    source_name: str | None = None,
    since_hours: int = Query(default=24, ge=1, le=720),
    limit: int = Query(default=200, ge=1, le=1000),
    cursor: str | None = Query(default=None, description="Opaque cursor from previous response next_cursor field"),
    latest_only: bool = Query(
        default=True,
        description=(
            "When true (default), return only the most recent record per canonical_product_id. "
            "Prevents stale older records from overwriting fresh data during incremental sync. "
            "Set to false to get the full history window (e.g. for backfill)."
        ),
    ),
) -> dict:
    """Export recent normalized product prices for poupi-baby consumption.

    Returns the N most recently collected products with a stable canonical_product_id,
    price, source URL and marketplace name.  Pass next_cursor into the cursor parameter
    to page through results when count == limit.

    By default (latest_only=true) only the single most-recent snapshot per product is
    returned — this guarantees the sync consumer always sees the freshest availability
    and price without older records overwriting them.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    if latest_only:
        # Use DISTINCT ON to return only the most recent row per canonical_product_id.
        # cursor-based pagination is not supported in this mode (ignored when present).
        store_filter = ""
        params: dict = {"since": since, "limit": limit}
        if source_name:
            store_filter = "AND store_name = :source_name"
            params["source_name"] = source_name

        sql = text(f"""
            SELECT DISTINCT ON (canonical_product_id)
                id, canonical_product_id, source_id, external_id, source_url,
                title, price::float, currency, availability, store_name, collected_at
            FROM normalized_products
            WHERE price IS NOT NULL
              AND canonical_product_id IS NOT NULL
              AND collected_at >= :since
              {store_filter}
            ORDER BY canonical_product_id, collected_at DESC, id DESC
            LIMIT :limit
        """)
        rows = db.execute(sql, params).fetchall()

        # Prometheus metrics
        price_feed_requests_total.labels(cursor_used="no").inc()
        price_feed_response_size.observe(len(rows))
        for row in rows:
            price_feed_items_served_total.labels(store_name=row.store_name or "unknown").inc()

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "since": since.isoformat(),
            "count": len(rows),
            "next_cursor": None,  # pagination not supported in latest_only mode
            "items": [
                {
                    "canonical_product_id": row.canonical_product_id,
                    "source_id": row.source_id,
                    "external_id": row.external_id,
                    "source_url": row.source_url,
                    "title": row.title,
                    "price": float(row.price),
                    "currency": row.currency or "BRL",
                    "availability": row.availability,
                    "store_name": row.store_name,
                    "collected_at": row.collected_at.isoformat() if row.collected_at else None,
                }
                for row in rows
            ],
        }

    # ── Full-history mode (latest_only=false) ─────────────────────────────────
    q = (
        db.query(NormalizedProduct)
        .filter(
            NormalizedProduct.price.isnot(None),
            NormalizedProduct.canonical_product_id.isnot(None),
            NormalizedProduct.collected_at >= since,
        )
        .order_by(NormalizedProduct.collected_at.desc(), NormalizedProduct.id.desc())
    )
    if source_name:
        q = q.filter(NormalizedProduct.store_name == source_name)

    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded:
            cur_ts, cur_id = decoded
            q = q.filter(
                or_(
                    NormalizedProduct.collected_at < cur_ts,
                    and_(
                        NormalizedProduct.collected_at == cur_ts,
                        NormalizedProduct.id < cur_id,
                    ),
                )
            )

    products = q.limit(limit).all()

    next_cursor = (
        _encode_cursor(products[-1].collected_at, products[-1].id)
        if len(products) == limit and products[-1].collected_at
        else None
    )

    # Prometheus metrics
    price_feed_requests_total.labels(cursor_used="yes" if cursor else "no").inc()
    price_feed_response_size.observe(len(products))
    for p in products:
        price_feed_items_served_total.labels(store_name=p.store_name or "unknown").inc()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "since": since.isoformat(),
        "count": len(products),
        "next_cursor": next_cursor,
        "items": [
            {
                "canonical_product_id": p.canonical_product_id,
                "source_id": p.source_id,
                "external_id": p.external_id,
                # source_url: direct product page link (from migration 0016, Phase E E-04 fix).
                # Populated by EcommerceProductNormalizer from raw.target_url.
                # May be None for records normalized before the migration.
                "source_url": p.source_url,
                "title": p.title,
                "price": float(p.price),
                "currency": p.currency or "BRL",
                "availability": p.availability,
                "store_name": p.store_name,
                "collected_at": p.collected_at.isoformat() if p.collected_at else None,
            }
            for p in products
        ],
    }

