ALTER TABLE "users"
ADD COLUMN "phone" VARCHAR(30),
ADD COLUMN "email_verified_at" TIMESTAMP(3),
ADD COLUMN "email_verification_code" VARCHAR(12),
ADD COLUMN "email_verification_expires_at" TIMESTAMP(3);
