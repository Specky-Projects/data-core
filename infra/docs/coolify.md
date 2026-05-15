# Coolify

## Organizacao

Crie um projeto Coolify por produto:

- `poupi-baby`;
- `data-core`;
- `trading-bot`;
- `dashboards`;
- `telegram-bots`.

Cada app/service deve ter variaveis proprias. Nao compartilhe `.env` entre projetos.

## Deploy via GitHub

Fluxo:

```text
GitHub push
  -> Coolify detecta alteracao
  -> build Docker
  -> deploy do recurso alterado
  -> health check
  -> restart seguro
```

## Dominios

Exemplos:

```text
app.example.com        Poupi Baby
api.example.com        Poupi Baby API
data-core.example.com  Data Core
dash.example.com       Dashboards
coolify.example.com    Painel Coolify
```

Configure DNS `A` apontando para o IP do Hetzner. Deixe SSL automatico ativo no Coolify.

## Servicos sem porta publica

Workers, bots long polling, schedulers e scrapers devem ficar sem dominio e sem porta publicada.

## Bancos no Coolify

Voce pode:

1. criar PostgreSQL compartilhado como recurso Coolify; ou
2. subir `infra/docker-compose.prod.yml` como stack compartilhada.

Para comecar, prefira recurso Coolify se quiser backup/logs integrados no painel. Prefira compose se quiser portabilidade total por Git.
