#!/bin/sh
set -e

echo "[entrypoint] Aguardando banco de dados..."

# Tenta conectar ao Postgres até 30s
MAX=30
i=0
until npx prisma db push --skip-generate 2>/dev/null || [ $i -ge $MAX ]; do
  i=$((i+1))
  echo "[entrypoint] Banco não disponível — tentativa $i/$MAX"
  sleep 1
done

if [ $i -ge $MAX ]; then
  echo "[entrypoint] ERRO: banco não ficou disponível em ${MAX}s"
  exit 1
fi

echo "[entrypoint] Banco disponível — executando migrações..."
npx prisma migrate deploy

echo "[entrypoint] Iniciando API..."
exec "$@"
