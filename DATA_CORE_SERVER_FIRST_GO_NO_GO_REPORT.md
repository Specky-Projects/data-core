# Data Core Server-First GO/NO-GO Report

Data da validação: 2026-06-01  
Ambiente: servidor `poupi` / Coolify resource `dvq6dwsagsw4p4oqwuw7bak9`  
Commit validado em runtime: `24ae50f`

## Diagnóstico

O Data Core deixou de depender de hot patch via notebook para os coletores Real Estate e Jobs.

Antes desta validação, o servidor ainda rodava imagem stale:

- `SOURCE_COMMIT=e29b868`
- imagens `dvq6dwsagsw4p4oqwuw7bak9_api:e29b868` e `dvq6dwsagsw4p4oqwuw7bak9_scheduler:e29b868`
- registry do container sem `real_estate.direct_agencies` e sem `jobs.gupy`

Foi identificado também um risco de deploy: a migration `0021_jobs_domain` apontava para `0020_signal_outcomes`, enquanto o banco do servidor estava em `0020_trading_signal_outcomes`.

## Ações Executadas

1. Corrigida a lineage da migration `0021_jobs_domain`.
2. Commit enviado para `main`: `24ae50f fix(migrations): align jobs domain migration lineage`.
3. Materializado checkout Git no servidor dentro do contexto de build do Coolify.
4. Preservados `.env` e `docker-compose.yaml` do Coolify.
5. Atualizados tags/env do compose para `24ae50f`.
6. Removida ambiguidade causada pelo `docker-compose.yml` do repo, renomeando-o para `docker-compose.repo-source.yml`.
7. Rebuild server-side executado com `docker compose build --no-cache`.
8. Runtime subido explicitamente com `docker compose -f docker-compose.yaml up -d`.
9. Executados smokes reais dentro do container API contra banco real.

## Evidências do Container

`docker compose -f docker-compose.yaml ps`:

```text
api        dvq6dwsagsw4p4oqwuw7bak9_api:24ae50f        Up healthy
scheduler  dvq6dwsagsw4p4oqwuw7bak9_scheduler:24ae50f  Up healthy
worker     dvq6dwsagsw4p4oqwuw7bak9_worker:24ae50f     Up healthy
```

Env redigido do container API:

```text
SOURCE_COMMIT=24ae50f
COOLIFY_BRANCH="main"
DATABASE_URL=<redacted>
REDIS_URL=<redacted>
```

Registry observado dentro do container:

```json
[
  "crypto.crypto_coin_ohlcv",
  "crypto.generic_price",
  "ecommerce.generic_product",
  "jobs.greenhouse",
  "jobs.gupy",
  "real_estate.direct_agencies",
  "real_estate.generic_listing",
  "sports_betting.generic_odds"
]
```

Migration/enum:

```text
alembic_version=0021_jobs_domain
enum_jobs=True
```

## Redis Status

`/health`:

```json
{
  "status": "ok",
  "dependencies": {
    "postgres": {"status": "ok"},
    "redis": {"status": "ok"}
  }
}
```

## Real Estate Smoke

Collector: `real_estate.direct_agencies`  
Perfil controlado: Razão, `max_pages=1`

Resultado persistido:

```json
{
  "run_id": "21a8f344-db3f-42c4-bb1b-2183f170068a",
  "status": "success",
  "items_collected": 24,
  "raw_saved_count": 24,
  "error_count": 0,
  "elapsed_seconds": 48.37,
  "module_raw_before": 134,
  "module_raw_after": 158,
  "collector_raw_before": 0,
  "collector_raw_after": 24
}
```

Payloads persistidos:

```text
agency_id=razao
agency=Imobiliaria Razao
strategy=json_ld
latest_collected_at=2026-06-01 01:59:33.600739+00:00
```

## Jobs Smoke

Collector: `jobs.gupy`  
Perfil controlado: termo `desenvolvedor`, `max_pages=1`

Resultado persistido:

```json
{
  "run_id": "6f7928cc-d22d-4d43-b79d-46954156aa05",
  "status": "success",
  "items_collected": 10,
  "raw_saved_count": 10,
  "error_count": 0,
  "elapsed_seconds": 21.62,
  "module_raw_before": 0,
  "module_raw_after": 10,
  "collector_raw_before": 0,
  "collector_raw_after": 10
}
```

Payloads persistidos:

```text
module=jobs
source_name=gupy
collector_name=jobs.gupy
latest_collected_at=2026-06-01 01:59:56.824593+00:00
sample companies/markers: Wise Group, Inicie, VENHA SER #SANGUELARANJA
```

## Readiness

`/live`:

```json
{"status":"alive","app":"data-core"}
```

`/ready`:

```json
{
  "ready": false,
  "checks": {
    "postgres": "ok",
    "redis": "ok",
    "operational": "BLOCKED"
  },
  "decision": "NO-GO",
  "blockers": ["no_ecommerce_provider_healthy"]
}
```

Observação: o bloqueio de `/ready` é operacional/ecommerce, não impediu a coleta real server-side de Real Estate e Jobs.

## Queries SQL Usadas

```sql
select version_num from alembic_version;
```

```sql
select exists(
  select 1
  from pg_enum
  where enumlabel='jobs'
    and enumtypid=(select oid from pg_type where typname='collectordomain')
);
```

```sql
select collector_name, status, items_collected, raw_saved_count, error_count,
       started_at, finished_at, id::text
from collection_runs
where collector_name in ('real_estate.direct_agencies', 'jobs.gupy')
order by started_at desc
limit 6;
```

```sql
select module, source_name, collector_name, count(*) as rows, max(collected_at) as latest
from raw_collections
where module in ('real_estate', 'jobs')
group by module, source_name, collector_name
order by module, source_name, collector_name;
```

```sql
select raw_json->>'agency_id' as agency_id,
       raw_json->>'agency' as agency,
       raw_json->>'strategy' as strategy,
       target_url,
       collected_at
from raw_collections
where collector_name='real_estate.direct_agencies'
order by collected_at desc
limit 5;
```

## Riscos Restantes

- `/ready` ainda retorna `ready=false` por `no_ecommerce_provider_healthy`.
- O scheduler amplo deve permanecer limitado por fonte até haver smokes graduais por coletor.
- O diretório do Coolify agora contém checkout Git para permitir rebuild server-side; futuros redeploys via UI devem preservar a mesma estratégia ou ajustar o pipeline do Coolify.
- Real Estate e Jobs foram validados com perfil controlado, não com carga ampla.

## Veredito

O Data Core está 100% server-first até coleta?

**SIM para Real Estate e Jobs em perfil controlado, com persistência real comprovada no servidor.**

**NÃO para readiness global do produto**, porque `/ready` ainda retorna `NO-GO` por dependência operacional de ecommerce.

Classificação final desta missão: **PARTIAL PASS**.
