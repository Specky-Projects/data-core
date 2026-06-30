"""merge WNBA and telegram observability heads

Revision ID: 0033_merge_wnba_telegram
Revises: 0004_wnba_module, 0032_telegram_observability
Create Date: 2026-06-21

This is an Alembic graph-only merge. It intentionally performs no schema or
data changes; both parent branches must already be applied before this revision.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0033_merge_wnba_telegram"
down_revision: tuple[str, str] = (
    "0004_wnba_module",
    "0032_telegram_observability",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
