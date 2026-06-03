"""0021_jobs_domain — adiciona valor 'jobs' ao enum CollectorDomain.

Necessário para: CollectorDefinition.domain, CollectionRun.domain,
CollectedRecord.domain — todos usam o enum collectordomain do PostgreSQL.

Nota: ALTER TYPE ... ADD VALUE não é transacional no PostgreSQL.
A migration usa op.execute() fora de transação (transactional_ddl=False).
"""

from __future__ import annotations

from alembic import op

revision: str = "0021_jobs_domain"
down_revision: str | None = "0020_signal_outcomes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD VALUE não é reversível em PostgreSQL sem recriar o enum.
    # Verificamos se o valor já existe antes de tentar adicionar
    # (idempotente em caso de re-run).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum
                WHERE enumlabel = 'jobs'
                  AND enumtypid = (
                      SELECT oid FROM pg_type WHERE typname = 'collectordomain'
                  )
            ) THEN
                ALTER TYPE collectordomain ADD VALUE 'jobs';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # PostgreSQL não suporta DROP VALUE de enum sem recriar o tipo.
    # Para rollback completo, seria necessário recriar o enum sem 'jobs'
    # e fazer cast de todas as colunas — operação destrutiva não implementada aqui.
    # Se necessário: recriar enum, alterar colunas, recriar constraints.
    pass
