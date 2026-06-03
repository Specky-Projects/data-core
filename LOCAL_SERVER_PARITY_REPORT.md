# Local Server Parity Report

Data: 2026-05-31

## Matriz

| Projeto | Local | Servidor | Classificacao | Evidencia |
|---|---|---|---|---|
| data-core | repo local com Real Estate/Jobs novos | Coolify app rodando imagem `e29b868` defasada | **DUPLICATED / STALE SERVER** | registry remoto inicial sem `real_estate.direct_agencies` e sem `jobs.*` |
| poupi-jobs | nao observado como repo local separado | `/opt/apps/poupi-jobs`, volume `poupi-jobs_pgdata`, network `poupi-jobs_default` | **SERVER ONLY / UNKNOWN HEALTH** | stack/volume existem, mas data-core `module=jobs` vazio |
| poupi-crypto | repo local existe | containers `poupi-crypto-api`, `poupi-crypto-volatile-api`, postgres e redis | **DUPLICATED / SERVER PRIMARY** | crypto gera `raw_collections` recentes no servidor |
| poupi-baby | repo local existe | API provavel, worker e volume observados | **DUPLICATED / SERVER PRIMARY PARTIAL** | worker healthy, API container observado; sem validacao funcional profunda nesta missao |
| poupi-frontend | repo local existe | container `wsp5l6d...:3000` observado | **DUPLICATED / SERVER PRIMARY PARTIAL** | container healthy, fora do escopo de coleta |
| poupi-brand | repo local existe | nao identificado diretamente em containers | **LOCAL ONLY / UNKNOWN** | sem container/stack com nome claro |

## Divergencia Principal

O servidor data-core nao estava rodando a mesma capacidade do local.

Registry remoto antes do hot patch:

```json
[
  "crypto.crypto_coin_ohlcv",
  "crypto.generic_price",
  "ecommerce.generic_product",
  "real_estate.generic_listing",
  "sports_betting.generic_odds"
]
```

Registry local/hot patch:

```text
real_estate.direct_agencies
jobs.gupy
jobs.greenhouse
jobs.lever
jobs.smartrecruiters
jobs.ashby
jobs.bamboohr
jobs.recruitee
jobs.workday
jobs.teamtailor
```

## Conclusao

O servidor nao era parity com o notebook no inicio da missao. Foi aplicado hot patch em containers para validar o caminho, mas ainda falta deploy duravel via imagem/Coolify para eliminar dependencia do notebook.

