ALTER TABLE "products"
  ADD COLUMN IF NOT EXISTS "product_family_name" VARCHAR(500),
  ADD COLUMN IF NOT EXISTS "product_family_slug" VARCHAR(500),
  ADD COLUMN IF NOT EXISTS "variant_label" VARCHAR(120),
  ADD COLUMN IF NOT EXISTS "measure_value" INTEGER,
  ADD COLUMN IF NOT EXISTS "measure_unit" VARCHAR(20);

CREATE INDEX IF NOT EXISTS "idx_products_family_slug"
  ON "products"("product_family_slug");
