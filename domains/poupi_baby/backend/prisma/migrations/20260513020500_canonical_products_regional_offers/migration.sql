ALTER TABLE "products"
  ADD COLUMN IF NOT EXISTS "canonical_name" VARCHAR(500),
  ADD COLUMN IF NOT EXISTS "ean" VARCHAR(32),
  ADD COLUMN IF NOT EXISTS "normalized_size" VARCHAR(80),
  ADD COLUMN IF NOT EXISTS "quantity" INTEGER,
  ADD COLUMN IF NOT EXISTS "unit_type" VARCHAR(40),
  ADD COLUMN IF NOT EXISTS "keywords" TEXT NOT NULL DEFAULT '[]';

UPDATE "products"
SET "canonical_name" = COALESCE("canonical_name", "title")
WHERE "canonical_name" IS NULL;

ALTER TABLE "offers"
  ADD COLUMN IF NOT EXISTS "current_price" DECIMAL(10,2),
  ADD COLUMN IF NOT EXISTS "original_price" DECIMAL(10,2),
  ADD COLUMN IF NOT EXISTS "price_per_unit" DECIMAL(10,4),
  ADD COLUMN IF NOT EXISTS "stock" INTEGER,
  ADD COLUMN IF NOT EXISTS "delivery_available" BOOLEAN,
  ADD COLUMN IF NOT EXISTS "pickup_available" BOOLEAN,
  ADD COLUMN IF NOT EXISTS "delivery_estimate" VARCHAR(120),
  ADD COLUMN IF NOT EXISTS "city" VARCHAR(120),
  ADD COLUMN IF NOT EXISTS "state" VARCHAR(2),
  ADD COLUMN IF NOT EXISTS "neighborhood" VARCHAR(120),
  ADD COLUMN IF NOT EXISTS "scraping_status" VARCHAR(40) NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS "last_scraped_at" TIMESTAMP(3),
  ADD COLUMN IF NOT EXISTS "last_valid_price" DECIMAL(10,2),
  ADD COLUMN IF NOT EXISTS "last_valid_scraped_at" TIMESTAMP(3);

UPDATE "offers"
SET
  "current_price" = COALESCE("current_price", "price"),
  "last_valid_price" = COALESCE("last_valid_price", "price"),
  "last_valid_scraped_at" = COALESCE("last_valid_scraped_at", "last_checked_at"),
  "last_scraped_at" = COALESCE("last_scraped_at", "last_checked_at"),
  "scraping_status" = COALESCE("scraping_status", 'success')
WHERE "deleted_at" IS NULL;

CREATE INDEX IF NOT EXISTS "idx_products_ean" ON "products"("ean");
CREATE INDEX IF NOT EXISTS "idx_products_canonical_match" ON "products"("brand", "normalized_size", "quantity");
CREATE INDEX IF NOT EXISTS "idx_offers_price_per_unit" ON "offers"("price_per_unit");
CREATE INDEX IF NOT EXISTS "idx_offers_region" ON "offers"("state", "city");
CREATE INDEX IF NOT EXISTS "idx_offers_scraping_status" ON "offers"("scraping_status");
CREATE INDEX IF NOT EXISTS "idx_offers_last_valid_scraped_at" ON "offers"("last_valid_scraped_at");
