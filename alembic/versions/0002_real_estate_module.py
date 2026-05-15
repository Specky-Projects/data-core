"""Add real estate collection module tables.

Revision ID: 0002_real_estate_module
Revises: 0001_initial_schema
Create Date: 2026-05-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_real_estate_module"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "real_estate_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_real_estate_sources_active"), "real_estate_sources", ["active"], unique=False)
    op.create_index(op.f("ix_real_estate_sources_city"), "real_estate_sources", ["city"], unique=False)
    op.create_index(op.f("ix_real_estate_sources_name"), "real_estate_sources", ["name"], unique=True)
    op.create_index(op.f("ix_real_estate_sources_state"), "real_estate_sources", ["state"], unique=False)

    op.create_table(
        "real_estate_listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("property_type", sa.String(length=80), nullable=True),
        sa.Column("purpose", sa.String(length=40), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("neighborhood", sa.String(length=160), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("bedrooms", sa.Integer(), nullable=True),
        sa.Column("bathrooms", sa.Integer(), nullable=True),
        sa.Column("parking_spaces", sa.Integer(), nullable=True),
        sa.Column("area_m2", sa.Integer(), nullable=True),
        sa.Column("condo_fee", sa.Numeric(14, 2), nullable=True),
        sa.Column("iptu", sa.Numeric(14, 2), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["real_estate_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "external_id", name="uq_real_estate_listing_source_external"),
        sa.UniqueConstraint("source_id", "url", name="uq_real_estate_listing_source_url"),
    )
    op.create_index(op.f("ix_real_estate_listings_active"), "real_estate_listings", ["active"], unique=False)
    op.create_index(
        "ix_real_estate_listing_city_neighborhood",
        "real_estate_listings",
        ["city", "neighborhood"],
        unique=False,
    )
    op.create_index(op.f("ix_real_estate_listings_city"), "real_estate_listings", ["city"], unique=False)
    op.create_index(
        op.f("ix_real_estate_listings_external_id"),
        "real_estate_listings",
        ["external_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_real_estate_listings_neighborhood"),
        "real_estate_listings",
        ["neighborhood"],
        unique=False,
    )
    op.create_index(op.f("ix_real_estate_listings_property_type"), "real_estate_listings", ["property_type"], unique=False)
    op.create_index(op.f("ix_real_estate_listings_purpose"), "real_estate_listings", ["purpose"], unique=False)
    op.create_index(op.f("ix_real_estate_listings_source_id"), "real_estate_listings", ["source_id"], unique=False)

    op.create_table(
        "real_estate_price_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("price", sa.Numeric(14, 2), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["real_estate_listings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_real_estate_price_listing_collected",
        "real_estate_price_history",
        ["listing_id", "collected_at"],
        unique=False,
    )
    op.create_index(op.f("ix_real_estate_price_history_collected_at"), "real_estate_price_history", ["collected_at"], unique=False)
    op.create_index(op.f("ix_real_estate_price_history_listing_id"), "real_estate_price_history", ["listing_id"], unique=False)

    op.create_table(
        "real_estate_raw_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["real_estate_listings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_real_estate_raw_pages_collected_at"), "real_estate_raw_pages", ["collected_at"], unique=False)
    op.create_index(op.f("ix_real_estate_raw_pages_listing_id"), "real_estate_raw_pages", ["listing_id"], unique=False)
    op.create_index(op.f("ix_real_estate_raw_pages_url"), "real_estate_raw_pages", ["url"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_real_estate_raw_pages_url"), table_name="real_estate_raw_pages")
    op.drop_index(op.f("ix_real_estate_raw_pages_listing_id"), table_name="real_estate_raw_pages")
    op.drop_index(op.f("ix_real_estate_raw_pages_collected_at"), table_name="real_estate_raw_pages")
    op.drop_table("real_estate_raw_pages")

    op.drop_index(op.f("ix_real_estate_price_history_listing_id"), table_name="real_estate_price_history")
    op.drop_index(op.f("ix_real_estate_price_history_collected_at"), table_name="real_estate_price_history")
    op.drop_index("ix_real_estate_price_listing_collected", table_name="real_estate_price_history")
    op.drop_table("real_estate_price_history")

    op.drop_index(op.f("ix_real_estate_listings_source_id"), table_name="real_estate_listings")
    op.drop_index(op.f("ix_real_estate_listings_purpose"), table_name="real_estate_listings")
    op.drop_index(op.f("ix_real_estate_listings_property_type"), table_name="real_estate_listings")
    op.drop_index(op.f("ix_real_estate_listings_neighborhood"), table_name="real_estate_listings")
    op.drop_index(op.f("ix_real_estate_listings_external_id"), table_name="real_estate_listings")
    op.drop_index(op.f("ix_real_estate_listings_city"), table_name="real_estate_listings")
    op.drop_index("ix_real_estate_listing_city_neighborhood", table_name="real_estate_listings")
    op.drop_index(op.f("ix_real_estate_listings_active"), table_name="real_estate_listings")
    op.drop_table("real_estate_listings")

    op.drop_index(op.f("ix_real_estate_sources_state"), table_name="real_estate_sources")
    op.drop_index(op.f("ix_real_estate_sources_name"), table_name="real_estate_sources")
    op.drop_index(op.f("ix_real_estate_sources_city"), table_name="real_estate_sources")
    op.drop_index(op.f("ix_real_estate_sources_active"), table_name="real_estate_sources")
    op.drop_table("real_estate_sources")
