"""Add versioned RAW collection and normalization metadata.

Revision ID: 0005_versioned_raw_normalization
Revises: 0004_flexible_raw_contract
Create Date: 2026-05-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_versioned_raw_normalization"
down_revision: str | None = "0004_flexible_raw_contract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NORMALIZED_TABLES = [
    "normalized_products",
    "normalized_real_estate_listings",
    "normalized_crypto_snapshots",
    "normalized_market_candles",
    "normalized_sports_odds",
]

ANALYTICS_TABLES = [
    "product_price_analytics",
    "real_estate_analytics",
    "crypto_analytics",
    "trading_analytics",
    "sports_odds_analytics",
]


def upgrade() -> None:
    op.add_column("raw_collections", sa.Column("collector_version", sa.String(length=40), server_default="1.0.0", nullable=False))
    op.add_column("raw_collections", sa.Column("raw_schema_name", sa.String(length=160), server_default="genericJson", nullable=False))
    op.add_column("raw_collections", sa.Column("raw_schema_version", sa.String(length=40), server_default="1.0.0", nullable=False))
    op.add_column(
        "raw_collections",
        sa.Column("collection_metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.create_index(op.f("ix_raw_collections_collector_version"), "raw_collections", ["collector_version"], unique=False)
    op.create_index(op.f("ix_raw_collections_raw_schema_name"), "raw_collections", ["raw_schema_name"], unique=False)
    op.create_index(op.f("ix_raw_collections_raw_schema_version"), "raw_collections", ["raw_schema_version"], unique=False)
    op.create_index("ix_raw_collections_schema", "raw_collections", ["module", "raw_schema_name", "raw_schema_version"], unique=False)

    op.add_column("collection_runs", sa.Column("collector_version", sa.String(length=40), nullable=True))
    op.add_column("collection_runs", sa.Column("raw_schema_name", sa.String(length=160), nullable=True))
    op.add_column("collection_runs", sa.Column("raw_schema_version", sa.String(length=40), nullable=True))
    op.create_index(op.f("ix_collection_runs_collector_version"), "collection_runs", ["collector_version"], unique=False)
    op.create_index(op.f("ix_collection_runs_raw_schema_name"), "collection_runs", ["raw_schema_name"], unique=False)
    op.create_index(op.f("ix_collection_runs_raw_schema_version"), "collection_runs", ["raw_schema_version"], unique=False)
    op.create_index("ix_collection_runs_schema", "collection_runs", ["module", "raw_schema_name", "raw_schema_version"], unique=False)

    op.create_table(
        "collector_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("collector_name", sa.String(length=160), nullable=False),
        sa.Column("collector_version", sa.String(length=40), nullable=False),
        sa.Column("raw_schema_name", sa.String(length=160), nullable=False),
        sa.Column("raw_schema_version", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "module",
            "source_name",
            "collector_name",
            "collector_version",
            "raw_schema_name",
            "raw_schema_version",
            name="uq_collector_version_identity",
        ),
    )
    for column in ["module", "source_name", "collector_name", "collector_version", "raw_schema_name", "raw_schema_version", "is_active"]:
        op.create_index(op.f(f"ix_collector_versions_{column}"), "collector_versions", [column], unique=False)

    for table in NORMALIZED_TABLES:
        op.add_column(table, sa.Column("normalizer_name", sa.String(length=160), nullable=True))
        op.add_column(table, sa.Column("normalizer_version", sa.String(length=40), nullable=True))
        op.add_column(table, sa.Column("normalized_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("normalization_metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
        op.add_column(table, sa.Column("source_raw_schema_name", sa.String(length=160), nullable=True))
        op.add_column(table, sa.Column("source_raw_schema_version", sa.String(length=40), nullable=True))
        op.add_column(table, sa.Column("source_collector_name", sa.String(length=160), nullable=True))
        op.add_column(table, sa.Column("source_collector_version", sa.String(length=40), nullable=True))
        for column in [
            "normalizer_name",
            "normalizer_version",
            "normalized_at",
            "source_raw_schema_name",
            "source_raw_schema_version",
            "source_collector_name",
            "source_collector_version",
        ]:
            op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)

    op.create_table(
        "normalizer_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=True),
        sa.Column("raw_schema_name", sa.String(length=160), nullable=False),
        sa.Column("raw_schema_version", sa.String(length=40), nullable=False),
        sa.Column("normalizer_name", sa.String(length=160), nullable=False),
        sa.Column("normalizer_version", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "module",
            "source_name",
            "raw_schema_name",
            "raw_schema_version",
            "normalizer_name",
            "normalizer_version",
            name="uq_normalizer_version_identity",
        ),
    )
    for column in ["module", "source_name", "raw_schema_name", "raw_schema_version", "normalizer_name", "normalizer_version", "is_active"]:
        op.create_index(op.f(f"ix_normalizer_versions_{column}"), "normalizer_versions", [column], unique=False)

    for table in ANALYTICS_TABLES:
        op.add_column(table, sa.Column("source_normalizer_name", sa.String(length=160), nullable=True))
        op.add_column(table, sa.Column("source_normalizer_version", sa.String(length=40), nullable=True))
        op.create_index(op.f(f"ix_{table}_source_normalizer_name"), table, ["source_normalizer_name"], unique=False)
        op.create_index(op.f(f"ix_{table}_source_normalizer_version"), table, ["source_normalizer_version"], unique=False)

    op.create_table(
        "data_quality_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=True),
        sa.Column("normalizer_name", sa.String(length=160), nullable=True),
        sa.Column("normalizer_version", sa.String(length=40), nullable=True),
        sa.Column("raw_schema_name", sa.String(length=160), nullable=True),
        sa.Column("raw_schema_version", sa.String(length=40), nullable=True),
        sa.Column("checked_count", sa.Integer(), nullable=False),
        sa.Column("passed_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("quality_score", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["module", "source_name", "normalizer_name", "normalizer_version", "raw_schema_name", "raw_schema_version", "status", "created_at"]:
        op.create_index(op.f(f"ix_data_quality_runs_{column}"), "data_quality_runs", [column], unique=False)


def downgrade() -> None:
    for column in ["module", "source_name", "normalizer_name", "normalizer_version", "raw_schema_name", "raw_schema_version", "status", "created_at"]:
        op.drop_index(op.f(f"ix_data_quality_runs_{column}"), table_name="data_quality_runs")
    op.drop_table("data_quality_runs")

    for table in ANALYTICS_TABLES:
        op.drop_index(op.f(f"ix_{table}_source_normalizer_version"), table_name=table)
        op.drop_index(op.f(f"ix_{table}_source_normalizer_name"), table_name=table)
        op.drop_column(table, "source_normalizer_version")
        op.drop_column(table, "source_normalizer_name")

    for column in ["module", "source_name", "raw_schema_name", "raw_schema_version", "normalizer_name", "normalizer_version", "is_active"]:
        op.drop_index(op.f(f"ix_normalizer_versions_{column}"), table_name="normalizer_versions")
    op.drop_table("normalizer_versions")

    for table in NORMALIZED_TABLES:
        for column in [
            "source_collector_version",
            "source_collector_name",
            "source_raw_schema_version",
            "source_raw_schema_name",
            "normalization_metadata_json",
            "normalized_at",
            "normalizer_version",
            "normalizer_name",
        ]:
            if column != "normalization_metadata_json":
                op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
            op.drop_column(table, column)

    for column in ["module", "source_name", "collector_name", "collector_version", "raw_schema_name", "raw_schema_version", "is_active"]:
        op.drop_index(op.f(f"ix_collector_versions_{column}"), table_name="collector_versions")
    op.drop_table("collector_versions")

    op.drop_index("ix_collection_runs_schema", table_name="collection_runs")
    op.drop_index(op.f("ix_collection_runs_raw_schema_version"), table_name="collection_runs")
    op.drop_index(op.f("ix_collection_runs_raw_schema_name"), table_name="collection_runs")
    op.drop_index(op.f("ix_collection_runs_collector_version"), table_name="collection_runs")
    op.drop_column("collection_runs", "raw_schema_version")
    op.drop_column("collection_runs", "raw_schema_name")
    op.drop_column("collection_runs", "collector_version")

    op.drop_index("ix_raw_collections_schema", table_name="raw_collections")
    op.drop_index(op.f("ix_raw_collections_raw_schema_version"), table_name="raw_collections")
    op.drop_index(op.f("ix_raw_collections_raw_schema_name"), table_name="raw_collections")
    op.drop_index(op.f("ix_raw_collections_collector_version"), table_name="raw_collections")
    op.drop_column("raw_collections", "collection_metadata_json")
    op.drop_column("raw_collections", "raw_schema_version")
    op.drop_column("raw_collections", "raw_schema_name")
    op.drop_column("raw_collections", "collector_version")
