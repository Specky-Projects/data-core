param(
  [string]$Module,
  [string]$Source,
  [string]$CollectorName,
  [int]$Limit = 100
)

$ErrorActionPreference = "Stop"

$python = @"
from scheduler.jobs import run_collection_targets_job
from database.session import SessionLocal
from app.raw.models import RawCollection
from app.normalization.models import NormalizedProduct
from app.analytics.models import ProductPriceAnalytics
from sqlalchemy import desc

result = run_collection_targets_job(
    module="$Module" or None,
    source="$Source" or None,
    collector_name="$CollectorName" or None,
    limit=$Limit,
)
db = SessionLocal()
try:
    latest_raw = db.query(RawCollection).order_by(desc(RawCollection.collected_at)).first()
    pending_raw = db.query(RawCollection).filter(RawCollection.processing_status == "normalization_pending").count()
    latest_product = db.query(NormalizedProduct).order_by(desc(NormalizedProduct.normalized_at), desc(NormalizedProduct.collected_at)).first()
    pending_analytics = db.query(NormalizedProduct).filter(NormalizedProduct.analytics_status == "pending").count()
    latest_analytics = db.query(ProductPriceAnalytics).order_by(desc(ProductPriceAnalytics.calculated_at)).first()
    result.update({
        "latest_raw_id": str(latest_raw.id) if latest_raw else None,
        "pending_raw": pending_raw,
        "latest_product_id": str(latest_product.id) if latest_product else None,
        "pending_product_analytics": pending_analytics,
        "latest_product_analytics_id": str(latest_analytics.id) if latest_analytics else None,
    })
finally:
    db.close()
print(result)
"@

$python | docker compose exec -T api python -
