# Ambientes

## Local

Use `docker-compose.local.yml` para desenvolvimento.

```bash
cd infra
cp .env.example .env
docker compose --env-file .env -f docker-compose.local.yml up -d
```

Portas locais:

- PostgreSQL: `localhost:5433`;
- Redis: `localhost:6380`.

SQLite continua aceitavel para testes pontuais, mas qualquer validacao parecida com producao deve usar PostgreSQL.

## Producao

Use Hetzner + Ubuntu 24.04 + Coolify.

Caracteristicas:

- PostgreSQL e Redis sem porta publicada;
- apps acessam servicos pela rede interna;
- SSL e reverse proxy gerenciados pelo Coolify;
- variaveis sensiveis configuradas por projeto;
- deploy independente por repositorio/app.

## Promocao de mudancas

1. Testar localmente com Docker.
2. Subir alteracao para GitHub.
3. Deixar o Coolify fazer build/deploy do projeto alterado.
4. Validar health check, logs e endpoint publico quando existir.
