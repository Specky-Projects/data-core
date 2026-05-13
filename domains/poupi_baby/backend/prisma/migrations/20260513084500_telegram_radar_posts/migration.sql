CREATE TABLE IF NOT EXISTS "telegram_posts" (
  "id" UUID NOT NULL DEFAULT gen_random_uuid(),
  "product_id" UUID NOT NULL,
  "offer_id" UUID NOT NULL,
  "chat_id" VARCHAR(120) NOT NULL,
  "message_hash" VARCHAR(64) NOT NULL,
  "price_snapshot" DECIMAL(10,2) NOT NULL,
  "score" DOUBLE PRECISION NOT NULL,
  "status" VARCHAR(30) NOT NULL DEFAULT 'sent',
  "reason" VARCHAR(500),
  "payload" TEXT NOT NULL DEFAULT '{}',
  "sent_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "telegram_posts_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "uq_telegram_posts_chat_hash"
  ON "telegram_posts"("chat_id", "message_hash");

CREATE INDEX IF NOT EXISTS "idx_telegram_posts_product_time"
  ON "telegram_posts"("product_id", "sent_at" DESC);

CREATE INDEX IF NOT EXISTS "idx_telegram_posts_offer_time"
  ON "telegram_posts"("offer_id", "sent_at" DESC);

CREATE INDEX IF NOT EXISTS "idx_telegram_posts_status_time"
  ON "telegram_posts"("status", "sent_at" DESC);
