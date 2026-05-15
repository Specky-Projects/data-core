param(
  [Parameter(Mandatory = $true)]
  [string]$Url,

  [string]$Source = "drogasil",
  [int]$TimeoutSeconds = 180,
  [switch]$SkipNormalize,
  [switch]$SkipAnalytics
)

$ErrorActionPreference = "Stop"
$skipNormalizePython = if ($SkipNormalize) { "True" } else { "False" }
$skipAnalyticsPython = if ($SkipAnalytics) { "True" } else { "False" }

$python = @"
from database.session import SessionLocal
from app.modules.ecommerce.collectors.poupi_legacy_collector import LegacyPoupiTarget, PoupiLegacyRawCollector
from scheduler.jobs import normalize_job, analytics_job
from app.raw.models import RawCollection
from app.normalization.models import NormalizedProduct
from app.analytics.models import ProductPriceAnalytics
from sqlalchemy import desc

db = SessionLocal()
try:
    result = PoupiLegacyRawCollector(db, timeout_seconds=$TimeoutSeconds).collect_targets([
        LegacyPoupiTarget(url="$Url", source_name="$Source", metadata={"manual_script": "run-poupi-legacy.ps1"})
    ])
finally:
    db.close()

if not ${skipNormalizePython}:
    normalize_job("ecommerce")
if not ${skipAnalyticsPython}:
    analytics_job("ecommerce")

db = SessionLocal()
try:
    latest_raw = db.query(RawCollection).filter(RawCollection.source_name == "$Source").order_by(desc(RawCollection.collected_at)).first()
    latest_product = db.query(NormalizedProduct).filter(NormalizedProduct.store_name == "$Source").order_by(desc(NormalizedProduct.normalized_at), desc(NormalizedProduct.collected_at)).first()
    latest_analytics = (
        db.query(ProductPriceAnalytics)
        .filter(ProductPriceAnalytics.product_id == latest_product.id)
        .order_by(desc(ProductPriceAnalytics.calculated_at))
        .first()
        if latest_product else None
    )
    pending_raw = db.query(RawCollection).filter(RawCollection.module == "ecommerce", RawCollection.processing_status == "normalization_pending").count()
    result.update({
        "latest_raw_id": str(latest_raw.id) if latest_raw else None,
        "pending_raw": pending_raw,
        "latest_product_id": str(latest_product.id) if latest_product else None,
        "latest_product_title": latest_product.title if latest_product else None,
        "latest_product_price": str(latest_product.price) if latest_product and latest_product.price is not None else None,
        "latest_product_analytics_id": str(latest_analytics.id) if latest_analytics else None,
    })
finally:
    db.close()
print(result)
"@

$python | docker compose exec -T api python -
