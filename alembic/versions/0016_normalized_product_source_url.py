"""Add source_url column to normalized_products.

source_url stores the original product page URL from the collector target
so that consumers (e.g. poupi-baby) can build "see product" deep links
without having to guess from external_id or source_id.

Populated by EcommerceProductNormalizer.normalize() from raw.target_url.
Nullable: existing rows will have NULL until re-normalization or backfill.

Revision ID: 0016_prod_source_url
Revises: 0015_pipeline_observability
Create Date: 2026-05-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_prod_source_url"
down_revision: str | None = "0015_pipeline_observability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "normalized_products",
        sa.Column("source_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("normalized_products", "source_url")
