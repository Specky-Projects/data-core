# Multi-Project Infra

Infraestrutura base para hospedar varios produtos no mesmo servidor Hetzner usando Ubuntu 24.04, Docker, Docker Compose, Coolify, PostgreSQL e Redis.

## Decisao inicial

Usar PostgreSQL compartilhado com um database e um usuario por projeto.

Motivos:

- menor custo de RAM/CPU em um servidor inicial;
- backup e manutencao mais simples;
- isolamento suficiente para a fase atual via databases, roles e permissoes;
- facil de migrar depois para PostgreSQL por projeto se algum produto crescer.

Redis comeca compartilhado, com prefixos/numeros de database por projeto. Projetos criticos podem ganhar Redis proprio depois.

## Estrutura

```text
infra/
  shared/
    postgres/
    redis/
    backups/
    monitoring/
  projects/
    poupi-baby/
    trading-bot/
    data-core/
    dashboards/
    telegram-bots/
  docs/
```

## Uso rapido

1. Leia `docs/server-bootstrap.md`.
2. Leia `docs/architecture.md`, `docs/environments.md` e `docs/multi-projects.md`.
3. Configure DNS para o servidor.
4. Instale Coolify.
5. Crie o recurso PostgreSQL compartilhado no Coolify ou suba `docker-compose.prod.yml`.
6. Crie um app por projeto no Coolify, apontando para o compose do projeto.
7. Configure variaveis por projeto usando os `.env.example`.

## Portas publicas

Publicas:

- `22/tcp` SSH;
- `80/tcp` HTTP;
- `443/tcp` HTTPS;
- painel Coolify apenas conforme configuracao do Coolify, idealmente com dominio proprio e HTTPS.

Nao publicar:

- PostgreSQL;
- Redis;
- workers;
- scrapers;
- bots sem webhook publico.
