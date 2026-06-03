# Real Estate Maturity Hardening Report

Data: 2026-05-31

## Objetivo

Elevar o dataset Real Estate de `MATURE com ressalvas` para `MATURE operacionalmente saudavel`, usando apenas evidencias persistidas no banco e replay real dos coletores.

## Resumo Executivo

Status final: **MATURE**

O hardening atingiu os dois criterios numericos principais:

- `price coverage geral`: **54.91% -> 76.17%**
- `Apolar concentration`: **79.10% -> 66.78%**

O ganho veio de duas correcoes:

- Promocao generica de `raw_data.offers.price` de JSON-LD para `structured_fields.price`.
- Ampliacao controlada da paginacao da fonte ja existente `razao` para 25 paginas.

Replay real final:

```text
collector_name = real_estate.direct_agencies
run_id = afe7bb41-673f-4bd3-a0a5-233003a3fa0d
status = success
started_at = 2026-05-31 13:02:28-03
finished_at = 2026-05-31 13:10:55-03
items_collected = 878
raw_saved_count = 878
error_count = 0
```

## Metricas Antes/Depois

| Metrica | Antes | Depois | Status |
|---|---:|---:|---|
| total de imoveis | 1517 | 2396 | PASS |
| price coverage | 54.91% | 76.17% | PASS |
| title coverage | 94.66% | 96.62% | PASS |
| city coverage | 82.53% | 95.41% | PASS |
| neighborhood coverage | 78.71% | 91.65% | PASS |
| listing_type coverage | 82.14% | 94.32% | PASS |
| completeness 5 campos | 78.59% | 90.83% | PASS |
| Apolar concentration | 79.10% | 66.78% | PASS |

## Metricas Finais Por Fonte

| Fonte | Registros | Preco | Price coverage | Title | City | Neighborhood | Listing type | Ultima coleta valida | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| apolar | 1600 | 1194 | 74.62% | 99.62% | 100.00% | 99.62% | 100.00% | 2026-05-31 13:10:49-03 | ativa/util |
| razao | 602 | 590 | 98.01% | 99.17% | 99.17% | 98.01% | 99.17% | 2026-05-31 13:10:55-03 | ativa/util |
| gonzaga | 76 | 0 | 0.00% | 47.37% | 14.47% | 14.47% | 0.00% | 2026-05-31 12:48:27-03 | ativa, mas subaproveitada/sem preco |
| imobiliariapacheco | 35 | 19 | 54.29% | 100.00% | 85.71% | 0.00% | 100.00% | 2026-05-29 20:58:22-03 | util parcial |
| imobiliariamaringa | 28 | 20 | 71.43% | 82.14% | 100.00% | 3.57% | 78.57% | 2026-05-31 12:16:41-03 | util parcial |
| cadena | 15 | 2 | 13.33% | 66.67% | 66.67% | 0.00% | 40.00% | 2026-05-31 12:16:41-03 | subaproveitada |
| j8 | 10 | 0 | 0.00% | 50.00% | 0.00% | 0.00% | 0.00% | 2026-05-31 12:16:43-03 | vazia para analytics |
| cibraco | 10 | 0 | 0.00% | 50.00% | 50.00% | 0.00% | 0.00% | 2026-05-31 12:16:40-03 | vazia para analytics |
| noruega | 10 | 0 | 0.00% | 50.00% | 50.00% | 0.00% | 0.00% | 2026-05-31 12:16:41-03 | vazia para analytics |
| prates | 10 | 0 | 0.00% | 50.00% | 0.00% | 0.00% | 0.00% | 2026-05-31 12:16:40-03 | vazia para analytics |

## Auditoria Dos Coletores

Coletores Real Estate registrados:

| Collector | Runs | Successes | Raw total | Ultimo raw | Diagnostico |
|---|---:|---:|---:|---|---|
| real_estate.direct_agencies | 14 | 9 | 2396 | 2026-05-31 13:10:55-03 | ativo, fonte operacional principal |
| real_estate.generic_listing | 0 | 0 | 0 | null | demo/mock, nao operacional |
| real_estate.imovelweb | 1 | 1 | 0 | null | vazio/bloqueado |
| real_estate.olx_imoveis | 1 | 1 | 0 | null | vazio/bloqueado |
| real_estate.viva_real | 1 | 1 | 0 | null | vazio/bloqueado |
| real_estate.zap_imoveis | 1 | 1 | 0 | null | vazio/bloqueado |

Conclusao: a unica rota operacional com dados persistidos reais e `real_estate.direct_agencies`. Os coletores de portais estao registrados, mas nao produzem raw persistido.

## Correcoes Aplicadas

### Price promotion

Root cause: fontes JSON-LD como Razao ja persistiam preco em:

```text
raw_data.offers.price
```

mas o extrator generico nao promovia esse valor para:

```text
structured_fields.price
```

Correcao:

- Extracao de `offers.price`, `lowPrice`, `highPrice` e `monthlyRentPrice`.
- Inferencia generica de `listing_type` a partir de URL e `businessFunction`.
- Promocao de `city`, `neighborhood`, `property_type` e `listing_code` quando disponiveis em JSON-LD.
- Fallback HTML passou a tentar preco por `R$ ...`, cidade, bairro, tipo e operacao.

### Razao pagination hardening

Root cause: Razao era uma fonte util, mas estava subcoletada. Auditoria HTTP real mostrou:

```text
pages 1-15: 24 JSON-LD/page, 24 precos/page
pages 16-25: 24 JSON-LD/page, maioria com preco
```

Correcao:

- `razao.max_pages = 25`.
- Evitar paginacao artificial em URLs que ja usam `pagina=`, impedindo combinacoes como `?pagina=5?page=5`.

## Evidencia De Banco

Metricas finais:

```text
total = 2396
price = 1825
title = 2315
city = 2286
neighborhood = 2196
listing_type = 2260
latest = 2026-05-31 13:10:55-03
```

Runs recentes:

```text
afe7bb41-673f-4bd3-a0a5-233003a3fa0d | success | raw_saved_count=878 | error_count=0
c12ae672-a98c-4828-9b8a-f5be2f216267 | success | raw_saved_count=0   | error_count=0
326d7b2e-4eb6-43d5-bd7c-cc9632299531 | success | raw_saved_count=1   | error_count=0
3862116a-0b2c-4cf4-861a-4314e96032e5 | success | raw_saved_count=607 | error_count=0
```

## Queries SQL Usadas

Metricas por fonte:

```sql
WITH rows AS (
  SELECT
    raw_json->>'agency_id' AS agency_id,
    raw_json->>'strategy' AS strategy,
    collected_at,
    raw_json->'structured_fields' AS sf
  FROM raw_collections
  WHERE module = 'real_estate'
    AND source_name = 'direct_agencies'
)
SELECT
  COALESCE(agency_id, 'unknown') AS agency_id,
  count(*) AS total,
  count(*) FILTER (WHERE sf->>'price' IS NOT NULL AND sf->>'price' <> '') AS price,
  count(*) FILTER (WHERE sf->>'title' IS NOT NULL AND sf->>'title' <> '') AS title,
  count(*) FILTER (WHERE sf->>'city' IS NOT NULL AND sf->>'city' <> '') AS city,
  count(*) FILTER (WHERE sf->>'neighborhood' IS NOT NULL AND sf->>'neighborhood' <> '') AS neighborhood,
  count(*) FILTER (WHERE sf->>'listing_type' IS NOT NULL AND sf->>'listing_type' <> '') AS listing_type,
  max(collected_at) AS last_valid_collection,
  string_agg(DISTINCT strategy, ',' ORDER BY strategy) AS strategies
FROM rows
GROUP BY 1
ORDER BY total DESC;
```

Metricas gerais:

```sql
WITH rows AS (
  SELECT raw_json->'structured_fields' AS sf, collected_at
  FROM raw_collections
  WHERE module = 'real_estate'
    AND source_name = 'direct_agencies'
)
SELECT
  count(*) AS total,
  count(*) FILTER (WHERE sf->>'price' IS NOT NULL AND sf->>'price' <> '') AS price,
  count(*) FILTER (WHERE sf->>'title' IS NOT NULL AND sf->>'title' <> '') AS title,
  count(*) FILTER (WHERE sf->>'city' IS NOT NULL AND sf->>'city' <> '') AS city,
  count(*) FILTER (WHERE sf->>'neighborhood' IS NOT NULL AND sf->>'neighborhood' <> '') AS neighborhood,
  count(*) FILTER (WHERE sf->>'listing_type' IS NOT NULL AND sf->>'listing_type' <> '') AS listing_type,
  max(collected_at) AS latest
FROM rows;
```

Runs:

```sql
SELECT
  id,
  status,
  started_at,
  finished_at,
  items_collected,
  raw_saved_count,
  error_count
FROM collection_runs
WHERE collector_name = 'real_estate.direct_agencies'
ORDER BY started_at DESC
LIMIT 5;
```

Coletores Real Estate:

```sql
SELECT
  collector_name,
  count(*) AS runs,
  count(*) FILTER (WHERE status::text = 'success') AS successes,
  max(started_at) AS latest_run,
  sum(raw_saved_count) AS raw_saved_total,
  sum(error_count) AS errors
FROM collection_runs
WHERE collector_name = ANY(:real_estate_collectors)
GROUP BY collector_name;
```

## Limitacoes E Riscos

- Gonzaga, J8, Cibraco, Noruega e Prates ainda nao sao fontes prontas para price analytics.
- Pacheco e Maringa sao uteis, mas pequenas.
- O replay final ainda exibiu avisos de `DirectAgencies listing fetch failed` em algumas agencias, embora o run tenha terminado `success` e `error_count=0`.
- A Razao ficou classificada com baixa confianca no campo `extraction_confidence`, apesar dos campos estarem presentes via JSON-LD. Isso e um refinamento de scoring, nao bloqueio de dados.

## Readiness

| Uso | Veredito | Justificativa |
|---|---|---|
| price monitoring | READY | 1825 imoveis com preco, coverage 76.17%, duas fontes principais com preco real: Apolar e Razao |
| analytics | READY | completeness 90.83%, city/neighborhood/listing_type acima de 90% |
| dashboard | READY | dados suficientes para visao operacional e analitica, com ressalva para rotular fontes subaproveitadas |
| producao | READY COM MONITORAMENTO | run real success, error_count=0, mas fontes secundarias ainda precisam health checks por agencia |

## Veredito Final

**MATURE**

O dataset Real Estate esta operacionalmente mais saudavel do que antes desta missao. A meta de price coverage foi superada, a concentracao da Apolar caiu abaixo de 70%, e a Razao virou uma segunda fonte relevante com 602 registros e 98.01% de price coverage.

