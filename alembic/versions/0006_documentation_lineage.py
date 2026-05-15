"""Add documentation and data lineage tables.

Revision ID: 0006_documentation_lineage
Revises: 0005_versioned_raw_normalization
Create Date: 2026-05-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_documentation_lineage"
down_revision: str | None = "0005_versioned_raw_normalization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_lineage",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=True),
        sa.Column("collector_name", sa.String(length=160), nullable=True),
        sa.Column("collector_version", sa.String(length=40), nullable=True),
        sa.Column("raw_schema_name", sa.String(length=160), nullable=True),
        sa.Column("raw_schema_version", sa.String(length=40), nullable=True),
        sa.Column("raw_collection_id", sa.UUID(), nullable=True),
        sa.Column("normalizer_name", sa.String(length=160), nullable=True),
        sa.Column("normalizer_version", sa.String(length=40), nullable=True),
        sa.Column("normalized_record_type", sa.String(length=160), nullable=True),
        sa.Column("normalized_record_id", sa.UUID(), nullable=True),
        sa.Column("analytics_processor_name", sa.String(length=160), nullable=True),
        sa.Column("analytics_processor_version", sa.String(length=40), nullable=True),
        sa.Column("analytics_record_type", sa.String(length=160), nullable=True),
        sa.Column("analytics_record_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "raw_collection_id",
            "normalized_record_type",
            "normalized_record_id",
            "analytics_record_type",
            "analytics_record_id",
            name="uq_data_lineage_path",
        ),
    )
    for column in [
        "module",
        "source_name",
        "collector_name",
        "collector_version",
        "raw_schema_name",
        "raw_schema_version",
        "raw_collection_id",
        "normalizer_name",
        "normalizer_version",
        "normalized_record_type",
        "normalized_record_id",
        "analytics_processor_name",
        "analytics_processor_version",
        "analytics_record_type",
        "analytics_record_id",
        "created_at",
    ]:
        op.create_index(op.f(f"ix_data_lineage_{column}"), "data_lineage", [column], unique=False)
    op.create_index("ix_data_lineage_raw_normalized", "data_lineage", ["raw_collection_id", "normalized_record_id"], unique=False)

    op.create_table(
        "schema_documentation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("schema_type", sa.String(length=80), nullable=False),
        sa.Column("schema_name", sa.String(length=160), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("fields_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("examples_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation_rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("relationships_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("module", "schema_type", "schema_name", "schema_version", name="uq_schema_documentation_identity"),
    )
    for column in ["module", "schema_type", "schema_name", "schema_version"]:
        op.create_index(op.f(f"ix_schema_documentation_{column}"), "schema_documentation", [column], unique=False)

    op.create_table(
        "entity_relationships",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("source_entity", sa.String(length=160), nullable=False),
        sa.Column("target_entity", sa.String(length=160), nullable=False),
        sa.Column("relationship_type", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("module", "source_entity", "target_entity", "relationship_type", name="uq_entity_relationship_identity"),
    )
    for column in ["module", "source_entity", "target_entity", "relationship_type"]:
        op.create_index(op.f(f"ix_entity_relationships_{column}"), "entity_relationships", [column], unique=False)

    op.create_table(
        "collector_documentation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=True),
        sa.Column("collector_name", sa.String(length=160), nullable=False),
        sa.Column("collector_version", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("supported_sources_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("supported_methods_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_schemas_generated_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("limitations_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collector_name", "collector_version", "source_name", name="uq_collector_documentation_identity"),
    )
    for column in ["module", "source_name", "collector_name", "collector_version"]:
        op.create_index(op.f(f"ix_collector_documentation_{column}"), "collector_documentation", [column], unique=False)

    op.create_table(
        "normalizer_documentation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("normalizer_name", sa.String(length=160), nullable=False),
        sa.Column("normalizer_version", sa.String(length=40), nullable=False),
        sa.Column("supported_raw_schemas_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generated_entities_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation_rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("quality_expectations_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalizer_name", "normalizer_version", name="uq_normalizer_documentation_identity"),
    )
    for column in ["module", "normalizer_name", "normalizer_version"]:
        op.create_index(op.f(f"ix_normalizer_documentation_{column}"), "normalizer_documentation", [column], unique=False)

    op.create_table(
        "analytics_documentation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("analytics_name", sa.String(length=160), nullable=False),
        sa.Column("analytics_version", sa.String(length=40), nullable=False),
        sa.Column("input_entities_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_entities_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generated_metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dependencies_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analytics_name", "analytics_version", name="uq_analytics_documentation_identity"),
    )
    for column in ["module", "analytics_name", "analytics_version"]:
        op.create_index(op.f(f"ix_analytics_documentation_{column}"), "analytics_documentation", [column], unique=False)


def downgrade() -> None:
    for column in ["module", "analytics_name", "analytics_version"]:
        op.drop_index(op.f(f"ix_analytics_documentation_{column}"), table_name="analytics_documentation")
    op.drop_table("analytics_documentation")

    for column in ["module", "normalizer_name", "normalizer_version"]:
        op.drop_index(op.f(f"ix_normalizer_documentation_{column}"), table_name="normalizer_documentation")
    op.drop_table("normalizer_documentation")

    for column in ["module", "source_name", "collector_name", "collector_version"]:
        op.drop_index(op.f(f"ix_collector_documentation_{column}"), table_name="collector_documentation")
    op.drop_table("collector_documentation")

    for column in ["module", "source_entity", "target_entity", "relationship_type"]:
        op.drop_index(op.f(f"ix_entity_relationships_{column}"), table_name="entity_relationships")
    op.drop_table("entity_relationships")

    for column in ["module", "schema_type", "schema_name", "schema_version"]:
        op.drop_index(op.f(f"ix_schema_documentation_{column}"), table_name="schema_documentation")
    op.drop_table("schema_documentation")

    op.drop_index("ix_data_lineage_raw_normalized", table_name="data_lineage")
    for column in [
        "module",
        "source_name",
        "collector_name",
        "collector_version",
        "raw_schema_name",
        "raw_schema_version",
        "raw_collection_id",
        "normalizer_name",
        "normalizer_version",
        "normalized_record_type",
        "normalized_record_id",
        "analytics_processor_name",
        "analytics_processor_version",
        "analytics_record_type",
        "analytics_record_id",
        "created_at",
    ]:
        op.drop_index(op.f(f"ix_data_lineage_{column}"), table_name="data_lineage")
    op.drop_table("data_lineage")
