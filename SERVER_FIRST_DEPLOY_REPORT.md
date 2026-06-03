# Server First Deploy Report

Data: 2026-05-31

## Objetivo

Validar se o servidor e a fonte operacional principal ate a camada de coleta.

## Deploy Observado

Data-core roda via Coolify:

```text
/data/coolify/applications/dvq6dwsagsw4p4oqwuw7bak9/docker-compose.yaml
services = api, scheduler, worker
image tag = e29b868
```

Restart policies:

```text
api = unless-stopped
scheduler = unless-stopped
worker = unless-stopped
```

Volumes:

```text
dvq6dwsagsw4p4oqwuw7bak9_runtime-logs
dvq6dwsagsw4p4oqwuw7bak9_runtime-data
```

Networks:

```text
infra_internal
coolify
dvq6dwsagsw4p4oqwuw7bak9
```

## Hot Patch Aplicado

Foi aplicado hot patch nos containers para expor os coletores novos e corrigir persistencia:

```text
collectors/real_estate/*.py
collectors/jobs/*.py
app/real_estate/*.py
utils/sanitization.py
workers/collector_worker.py
collectors/registry.py
database/models.py
```

Importante: isso **nao e deploy duravel**. Sera perdido em rebuild/redeploy do Coolify se o codigo nao for incorporado a imagem.

## Health

```text
/live = alive
/health = degraded por Redis
/ready = timeout
```

Redis:

```text
max requests limit exceeded. Limit: 500000, Usage: 500000
```

## Backup

Backups minimos existem como artefato local no repo:

```text
deploy/backup.sh
```

Nao foi validado restore nesta missao.

## Rollback

Rollback seguro:

1. Rebuild/redeploy Coolify para voltar a imagem `e29b868` sem hot patch.
2. Restaurar `collector_definitions.config` de `real_estate.direct_agencies` se necessario.
3. Manter o enum `jobs`; rollback desse enum nao e trivial no PostgreSQL e nao deve ser tentado sem janela de manutencao.

## Veredito

**PARTIAL / NO-GO para server-first collection**

Infra existe, mas a versao server-side estava stale, Redis esta degradado e as coletas prioritarias nao terminaram com sucesso.

