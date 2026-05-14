"""Add sports odds collection module tables.

Revision ID: 0003_sports_odds_module
Revises: 0002_real_estate_module
Create Date: 2026-05-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_sports_odds_module"
down_revision: str | None = "0002_real_estate_module"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sportsbooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sportsbooks_active"), "sportsbooks", ["active"], unique=False)
    op.create_index(op.f("ix_sportsbooks_name"), "sportsbooks", ["name"], unique=True)

    op.create_table(
        "sports_leagues",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sport", sa.String(length=80), nullable=False),
        sa.Column("league_name", sa.String(length=120), nullable=False),
        sa.Column("country", sa.String(length=80), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sport", "league_name", "country", name="uq_sports_league_identity"),
    )
    op.create_index(op.f("ix_sports_leagues_active"), "sports_leagues", ["active"], unique=False)
    op.create_index(op.f("ix_sports_leagues_country"), "sports_leagues", ["country"], unique=False)
    op.create_index(op.f("ix_sports_leagues_league_name"), "sports_leagues", ["league_name"], unique=False)
    op.create_index(op.f("ix_sports_leagues_sport"), "sports_leagues", ["sport"], unique=False)

    op.create_table(
        "sports_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("league_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("home_team", sa.String(length=160), nullable=False),
        sa.Column("away_team", sa.String(length=160), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["league_id"], ["sports_leagues.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "external_id", name="uq_sports_event_league_external"),
    )
    op.create_index(op.f("ix_sports_events_away_team"), "sports_events", ["away_team"], unique=False)
    op.create_index(op.f("ix_sports_events_event_status"), "sports_events", ["event_status"], unique=False)
    op.create_index(op.f("ix_sports_events_external_id"), "sports_events", ["external_id"], unique=False)
    op.create_index(op.f("ix_sports_events_home_team"), "sports_events", ["home_team"], unique=False)
    op.create_index(op.f("ix_sports_events_league_id"), "sports_events", ["league_id"], unique=False)
    op.create_index("ix_sports_event_matchup_start", "sports_events", ["home_team", "away_team", "start_time"], unique=False)
    op.create_index(op.f("ix_sports_events_start_time"), "sports_events", ["start_time"], unique=False)

    op.create_table(
        "sports_markets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("market_type", sa.String(length=80), nullable=False),
        sa.Column("selection", sa.String(length=160), nullable=False),
        sa.Column("handicap", sa.Numeric(10, 2), nullable=True),
        sa.Column("bookmaker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["bookmaker_id"], ["sportsbooks.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["sports_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id",
            "bookmaker_id",
            "market_type",
            "selection",
            "handicap",
            name="uq_sports_market_identity",
        ),
    )
    op.create_index(op.f("ix_sports_markets_bookmaker_id"), "sports_markets", ["bookmaker_id"], unique=False)
    op.create_index(op.f("ix_sports_markets_event_id"), "sports_markets", ["event_id"], unique=False)
    op.create_index(op.f("ix_sports_markets_market_type"), "sports_markets", ["market_type"], unique=False)
    op.create_index(op.f("ix_sports_markets_selection"), "sports_markets", ["selection"], unique=False)

    op.create_table(
        "sports_odds_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("odd", sa.Numeric(10, 4), nullable=False),
        sa.Column("implied_probability", sa.Numeric(10, 6), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["sports_markets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sports_odds_snapshots_collected_at"), "sports_odds_snapshots", ["collected_at"], unique=False)
    op.create_index(op.f("ix_sports_odds_snapshots_market_id"), "sports_odds_snapshots", ["market_id"], unique=False)
    op.create_index("ix_sports_odds_market_collected", "sports_odds_snapshots", ["market_id", "collected_at"], unique=False)

    op.create_table(
        "sports_raw_payloads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sportsbook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["sportsbook_id"], ["sportsbooks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sports_raw_payloads_collected_at"), "sports_raw_payloads", ["collected_at"], unique=False)
    op.create_index(op.f("ix_sports_raw_payloads_sportsbook_id"), "sports_raw_payloads", ["sportsbook_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sports_raw_payloads_sportsbook_id"), table_name="sports_raw_payloads")
    op.drop_index(op.f("ix_sports_raw_payloads_collected_at"), table_name="sports_raw_payloads")
    op.drop_table("sports_raw_payloads")

    op.drop_index("ix_sports_odds_market_collected", table_name="sports_odds_snapshots")
    op.drop_index(op.f("ix_sports_odds_snapshots_market_id"), table_name="sports_odds_snapshots")
    op.drop_index(op.f("ix_sports_odds_snapshots_collected_at"), table_name="sports_odds_snapshots")
    op.drop_table("sports_odds_snapshots")

    op.drop_index(op.f("ix_sports_markets_selection"), table_name="sports_markets")
    op.drop_index(op.f("ix_sports_markets_market_type"), table_name="sports_markets")
    op.drop_index(op.f("ix_sports_markets_event_id"), table_name="sports_markets")
    op.drop_index(op.f("ix_sports_markets_bookmaker_id"), table_name="sports_markets")
    op.drop_table("sports_markets")

    op.drop_index(op.f("ix_sports_events_start_time"), table_name="sports_events")
    op.drop_index("ix_sports_event_matchup_start", table_name="sports_events")
    op.drop_index(op.f("ix_sports_events_league_id"), table_name="sports_events")
    op.drop_index(op.f("ix_sports_events_home_team"), table_name="sports_events")
    op.drop_index(op.f("ix_sports_events_external_id"), table_name="sports_events")
    op.drop_index(op.f("ix_sports_events_event_status"), table_name="sports_events")
    op.drop_index(op.f("ix_sports_events_away_team"), table_name="sports_events")
    op.drop_table("sports_events")

    op.drop_index(op.f("ix_sports_leagues_sport"), table_name="sports_leagues")
    op.drop_index(op.f("ix_sports_leagues_league_name"), table_name="sports_leagues")
    op.drop_index(op.f("ix_sports_leagues_country"), table_name="sports_leagues")
    op.drop_index(op.f("ix_sports_leagues_active"), table_name="sports_leagues")
    op.drop_table("sports_leagues")

    op.drop_index(op.f("ix_sportsbooks_name"), table_name="sportsbooks")
    op.drop_index(op.f("ix_sportsbooks_active"), table_name="sportsbooks")
    op.drop_table("sportsbooks")
