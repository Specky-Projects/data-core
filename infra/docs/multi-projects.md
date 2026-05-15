# Multi-Projetos

## Principios

- Cada projeto tem compose, variaveis, logs e deploy independentes.
- Projetos HTTP usam dominio/subdominio proprio no Coolify.
- Workers, scrapers e bots sem webhook ficam sem porta publica.
- Banco e Redis ficam na rede interna.
- Pausar ou atualizar um projeto nao deve reiniciar os demais.

## Padrao por projeto

```text
projects/<nome>/
  .env.example
  docker-compose.prod.yml
  README.md
```

O `.env` real deve ser criado no Coolify ou no servidor e nunca versionado.

## Redes conectadas

Cada projeto de producao deve entrar em duas redes:

- rede propria do app, por exemplo `data_core_app`, para saida HTTP e reverse proxy;
- rede compartilhada `infra_internal`, para acessar PostgreSQL, Redis e monitoramento interno.

Servicos que precisam ser descobertos por outros stacks devem declarar alias estavel na `infra_internal`.

Aliases iniciais:

- `postgres:5432`;
- `redis:6379`;
- `data-core-api:8000`;
- `poupi-baby-api:3000`;
- `trading-bot-runner`.

## Quando criar servico separado

Crie containers separados para processos com ciclo de vida diferente:

- API web;
- worker de fila;
- scheduler;
- scraper;
- bot Telegram;
- dashboard interno.

Isso permite reiniciar somente o componente afetado e deixa logs mais claros.

## Nomes recomendados

- projetos: `poupi-baby`, `data-core`, `trading-bot`;
- databases: `poupi_baby_db`, `data_core_db`, `trading_bot_db`;
- usuarios: `poupi_baby_user`, `data_core_user`, `trading_bot_user`;
- dominios: `app.exemplo.com`, `api.exemplo.com`, `data-core.exemplo.com`.
