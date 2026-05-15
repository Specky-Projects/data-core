# Poupi Baby

Deploy recomendado no Coolify:

- criar novo projeto `poupi-baby`;
- conectar repositorio GitHub;
- usar Dockerfile do backend para API e `worker/Dockerfile` para worker;
- adicionar dominio publico para API/app;
- configurar `.env` com `DATABASE_URL` e `REDIS_URL` internos;
- configurar `DATA_CORE_URL=http://data-core-api:8000` e `DATA_CORE_API_KEY`;
- manter workers sem porta publica.
- conectar na rede compartilhada `infra_internal`.
- usar alias interno `poupi-baby-api` para monitoramento e integracoes privadas.

Banco:

```text
poupi_baby_db
poupi_baby_user
```

Redis sugerido: DB `1`.

API interna:

```text
poupi-baby-api:3001
```

Health check:

```text
GET /healthz
```

## Observacoes de deploy

O compose deste diretorio e um template operacional. Localmente ele assume que o repo irmao existe em `../../../../poupi-baby`; no Coolify, use o repositorio do Poupi Baby como origem do build ou configure `POUPI_BABY_REPO_PATH`.

O worker aguarda a API ficar saudavel para reduzir risco de iniciar antes das migrations Prisma do backend.
