"""add_nba_quant_engine

Revision ID: 74f248e42006
Revises: 34735fc7e2a2
Create Date: 2026-06-07 20:10:14.407293
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '74f248e42006'
down_revision: str | None = '34735fc7e2a2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('nba_edge_registry',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('setup_name', sa.String(length=80), nullable=False),
    sa.Column('total_bets', sa.Integer(), nullable=False),
    sa.Column('wins', sa.Integer(), nullable=False),
    sa.Column('losses', sa.Integer(), nullable=False),
    sa.Column('pending', sa.Integer(), nullable=False),
    sa.Column('void', sa.Integer(), nullable=False),
    sa.Column('roi', sa.Float(), nullable=False),
    sa.Column('yield_pct', sa.Float(), nullable=False),
    sa.Column('win_rate', sa.Float(), nullable=False),
    sa.Column('profit_factor', sa.Float(), nullable=False),
    sa.Column('expectancy', sa.Float(), nullable=False),
    sa.Column('max_drawdown', sa.Float(), nullable=False),
    sa.Column('classification', sa.Enum('profitable', 'neutral', 'losing', name='edgeclassification'), nullable=False),  # noqa: E501
    sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_nba_edge_registry_classification'), 'nba_edge_registry', ['classification'], unique=False)  # noqa: E501
    op.create_index(op.f('ix_nba_edge_registry_setup_name'), 'nba_edge_registry', ['setup_name'], unique=True)  # noqa: E501
    op.create_table('nba_games',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('external_id', sa.String(length=80), nullable=True),
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('game_date', sa.DateTime(timezone=True), nullable=False),
    sa.Column('home_team', sa.String(length=160), nullable=False),
    sa.Column('away_team', sa.String(length=160), nullable=False),
    sa.Column('home_score', sa.Integer(), nullable=True),
    sa.Column('away_score', sa.Integer(), nullable=True),
    sa.Column('status', sa.Enum('scheduled', 'live', 'final', name='gamestatus'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('home_team', 'away_team', 'game_date', name='uq_nba_game_matchup')
    )
    op.create_index(op.f('ix_nba_games_away_team'), 'nba_games', ['away_team'], unique=False)
    op.create_index(op.f('ix_nba_games_external_id'), 'nba_games', ['external_id'], unique=False)
    op.create_index(op.f('ix_nba_games_game_date'), 'nba_games', ['game_date'], unique=False)
    op.create_index(op.f('ix_nba_games_home_team'), 'nba_games', ['home_team'], unique=False)
    op.create_index(op.f('ix_nba_games_season'), 'nba_games', ['season'], unique=False)
    op.create_index('ix_nba_games_season_date', 'nba_games', ['season', 'game_date'], unique=False)
    op.create_index(op.f('ix_nba_games_status'), 'nba_games', ['status'], unique=False)
    op.create_index('ix_nba_games_status_date', 'nba_games', ['status', 'game_date'], unique=False)
    op.create_table('nba_features',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('game_id', sa.UUID(), nullable=False),
    sa.Column('home_rest_days', sa.Integer(), nullable=True),
    sa.Column('away_rest_days', sa.Integer(), nullable=True),
    sa.Column('home_back_to_back', sa.Boolean(), nullable=False),
    sa.Column('away_back_to_back', sa.Boolean(), nullable=False),
    sa.Column('home_last5_wins', sa.Integer(), nullable=True),
    sa.Column('home_last5_games', sa.Integer(), nullable=True),
    sa.Column('away_last5_wins', sa.Integer(), nullable=True),
    sa.Column('away_last5_games', sa.Integer(), nullable=True),
    sa.Column('home_last10_wins', sa.Integer(), nullable=True),
    sa.Column('home_last10_games', sa.Integer(), nullable=True),
    sa.Column('away_last10_wins', sa.Integer(), nullable=True),
    sa.Column('away_last10_games', sa.Integer(), nullable=True),
    sa.Column('home_off_rtg', sa.Float(), nullable=True),
    sa.Column('away_off_rtg', sa.Float(), nullable=True),
    sa.Column('home_def_rtg', sa.Float(), nullable=True),
    sa.Column('away_def_rtg', sa.Float(), nullable=True),
    sa.Column('home_pace', sa.Float(), nullable=True),
    sa.Column('away_pace', sa.Float(), nullable=True),
    sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
    sa.ForeignKeyConstraint(['game_id'], ['nba_games.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_nba_features_game_id'), 'nba_features', ['game_id'], unique=True)
    op.create_table('nba_odds',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('game_id', sa.UUID(), nullable=False),
    sa.Column('bookmaker', sa.String(length=80), nullable=False),
    sa.Column('market_type', sa.Enum('moneyline', 'spread', 'totals', name='markettype'), nullable=False),  # noqa: E501
    sa.Column('selection', sa.String(length=160), nullable=False),
    sa.Column('line', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('odd', sa.Numeric(precision=8, scale=4), nullable=False),
    sa.Column('collected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
    sa.ForeignKeyConstraint(['game_id'], ['nba_games.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('game_id', 'bookmaker', 'market_type', 'selection', name='uq_nba_odds_market')  # noqa: E501
    )
    op.create_index(op.f('ix_nba_odds_bookmaker'), 'nba_odds', ['bookmaker'], unique=False)
    op.create_index(op.f('ix_nba_odds_game_id'), 'nba_odds', ['game_id'], unique=False)
    op.create_index('ix_nba_odds_game_market', 'nba_odds', ['game_id', 'market_type'], unique=False)
    op.create_index(op.f('ix_nba_odds_market_type'), 'nba_odds', ['market_type'], unique=False)
    op.create_table('nba_signals',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('game_id', sa.UUID(), nullable=False),
    sa.Column('setup_name', sa.String(length=80), nullable=False),
    sa.Column('market_type', sa.Enum('moneyline', 'spread', 'totals', name='markettype'), nullable=False),  # noqa: E501
    sa.Column('selection', sa.String(length=160), nullable=False),
    sa.Column('line', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('odd', sa.Numeric(precision=8, scale=4), nullable=False),
    sa.Column('signal_direction', sa.Enum('home', 'away', 'over', 'under', name='signaldirection'), nullable=False),  # noqa: E501
    sa.Column('rationale', sa.Text(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
    sa.ForeignKeyConstraint(['game_id'], ['nba_games.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('game_id', 'setup_name', name='uq_nba_signal_game_setup')
    )
    op.create_index(op.f('ix_nba_signals_created_at'), 'nba_signals', ['created_at'], unique=False)
    op.create_index(op.f('ix_nba_signals_game_id'), 'nba_signals', ['game_id'], unique=False)
    op.create_index('ix_nba_signals_setup_created', 'nba_signals', ['setup_name', 'created_at'], unique=False)  # noqa: E501
    op.create_index(op.f('ix_nba_signals_setup_name'), 'nba_signals', ['setup_name'], unique=False)
    op.create_table('nba_quant_bets',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('signal_id', sa.UUID(), nullable=False),
    sa.Column('stake', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('status', sa.Enum('pending', 'won', 'lost', 'void', name='betstatus'), nullable=False),  # noqa: E501
    sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('pnl', sa.Numeric(precision=12, scale=4), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),  # noqa: E501
    sa.ForeignKeyConstraint(['signal_id'], ['nba_signals.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_nba_quant_bets_signal_id'), 'nba_quant_bets', ['signal_id'], unique=True)  # noqa: E501
    op.create_index(op.f('ix_nba_quant_bets_status'), 'nba_quant_bets', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_nba_quant_bets_status'), table_name='nba_quant_bets')
    op.drop_index(op.f('ix_nba_quant_bets_signal_id'), table_name='nba_quant_bets')
    op.drop_table('nba_quant_bets')
    op.drop_index(op.f('ix_nba_signals_setup_name'), table_name='nba_signals')
    op.drop_index('ix_nba_signals_setup_created', table_name='nba_signals')
    op.drop_index(op.f('ix_nba_signals_game_id'), table_name='nba_signals')
    op.drop_index(op.f('ix_nba_signals_created_at'), table_name='nba_signals')
    op.drop_table('nba_signals')
    op.drop_index(op.f('ix_nba_odds_market_type'), table_name='nba_odds')
    op.drop_index('ix_nba_odds_game_market', table_name='nba_odds')
    op.drop_index(op.f('ix_nba_odds_game_id'), table_name='nba_odds')
    op.drop_index(op.f('ix_nba_odds_bookmaker'), table_name='nba_odds')
    op.drop_table('nba_odds')
    op.drop_index(op.f('ix_nba_features_game_id'), table_name='nba_features')
    op.drop_table('nba_features')
    op.drop_index('ix_nba_games_status_date', table_name='nba_games')
    op.drop_index(op.f('ix_nba_games_status'), table_name='nba_games')
    op.drop_index('ix_nba_games_season_date', table_name='nba_games')
    op.drop_index(op.f('ix_nba_games_season'), table_name='nba_games')
    op.drop_index(op.f('ix_nba_games_home_team'), table_name='nba_games')
    op.drop_index(op.f('ix_nba_games_game_date'), table_name='nba_games')
    op.drop_index(op.f('ix_nba_games_external_id'), table_name='nba_games')
    op.drop_index(op.f('ix_nba_games_away_team'), table_name='nba_games')
    op.drop_table('nba_games')
    op.drop_index(op.f('ix_nba_edge_registry_setup_name'), table_name='nba_edge_registry')
    op.drop_index(op.f('ix_nba_edge_registry_classification'), table_name='nba_edge_registry')
    op.drop_table('nba_edge_registry')
    op.execute("DROP TYPE IF EXISTS betstatus")
    op.execute("DROP TYPE IF EXISTS signaldirection")
    op.execute("DROP TYPE IF EXISTS markettype")
    op.execute("DROP TYPE IF EXISTS gamestatus")
    op.execute("DROP TYPE IF EXISTS edgeclassification")
