# PHASE I REPORT — Telegram Group Distribution & Crypto Research QA

> Executed: 2026-05-16
> Scope: poupi-baby (Trilha A) + data-core crypto research QA (Trilha B)
> Fases: 1–13

---

## Resumo Executivo

Phase I executou duas trilhas paralelas: infraestrutura completa para distribuição
de oportunidades em grupos Telegram (poupi-baby) e camada de QA/ranking para a
pesquisa quantitativa crypto (data-core).

**Trilha A**: TelegramGroup + TelegramGroupPost (Prisma), rate limiter Redis,
publisher BullMQ, processor, métricas Prometheus, 5 painéis Grafana adicionais.

**Trilha B**: ExperimentQA (validação de registros), StrategyRanker (score composto),
DatasetQA (qualidade OHLCV fleet-wide).

**Total de artefatos**: 14 novos / complementados.

---

## Auditoria Pre-Implementation (Anti-Duplicação)

| Item auditado | Resultado | Decisão |
|---|---|---|
| TelegramService.sendMessage() | ✅ Existe em NotificationsModule | Reutilizado pelo processor — sem duplicação |
| TelegramPost (dedup existente) | ✅ chatId + messageHash unique | Nova tabela TelegramGroupPost usa groupId + messageHash (semântica diferente) |
| NOTIFICATION_QUEUE | ✅ Existe para users individuais | TELEGRAM_GROUP_QUEUE criado separado — rate limiting diferente |
| CacheService.increment() | ❌ Ausente | Adicionado sem quebrar API existente |
| ohlcv_integrity.check_integrity() | ✅ Existe (Phase H) | dataset_qa.py usa como base — sem duplicação |
| ExperimentTracker | ✅ Existe (Phase H) | experiment_qa.py e strategy_ranker.py reutilizam |
| StrategyRegistry | ✅ Existe (Phase H) | strategy_ranker.py faz lookup de canonical params |

---

## TRILHA A — POUPI BABY

### Fase 2 — Modelos Prisma

**Complementado** `prisma/schema.prisma`:

**`TelegramGroup`**:
- chatId (unique), name, category, active, priority
- maxPerDay, minIntervalMinutes, minDealScore
- allowedCategories (JSON string[]), bannedKeywords (JSON string[])
- totalPosted, totalFailed, lastPostedAt
- Índices: active + priority, category + active

**`TelegramGroupPost`**:
- groupId → TelegramGroup, productId, offerId
- messageHash: sha256(productId:offerId:price.toFixed(2)) — dedup key
- priceSnapshot, dealScore, status (sent|failed|skipped|rate_limited)
- failReason, clickCount, payload JSON
- `@@unique([groupId, messageHash])` — mesmo produto/preço não reenviado ao mesmo grupo

### Fase 2 — Queue Constants

**Complementado** `shared/queues/queue.constants.ts`:
- `TELEGRAM_GROUP_QUEUE = 'telegram-group'`
- `TELEGRAM_GROUP_JOB = 'publish-group-opportunity'`
- `TelegramGroupJobData` interface completa
- `TELEGRAM_GROUP_JOB_DEFAULTS`: attempts=2, exponential 10s

### Fase 3 — TelegramGroupsService

**Criado** `telegram-groups/telegram-groups.service.ts`:
- `findAll()`, `findActive()`, `findById()` — consultas com deletedAt guard
- `create()`, `update()`, `deactivate()` — CRUD completo
- `selectEligibleGroups(opp, messageHash)` — filtragem por score + categoria + bannedKeywords + dedup DB
- `recordPost()` — persistência idempotente (ignora conflito de hash)
- `getStats(groupId, days)` — totalSent/Failed/RateLimited/Skipped, uniqueProducts, avgDealScore
- `buildMessageHash(productId, offerId, price)` — sha256 estático

### Fase 4 — TelegramGroupRateLimiter

**Criado** `telegram-groups/telegram-group-rate-limiter.service.ts`:
- `check(group)` → `{ allowed, reason?, dailyCount? }` — sem side effects
- `recordPost(group)` — incrementa diário + ativa cooldown de intervalo
- `getDailyCount(groupId)` — conta publicações no dia UTC atual
- `reset(groupId)` — admin reset
- Redis keys:
  - `tg:group:<id>:daily:<YYYY-MM-DD>` — TTL 25h (absorve drift de clock)
  - `tg:group:<id>:interval` — TTL = minIntervalMinutes * 60s

**Complementado** `cache/cache.service.ts`:
- `increment(key, ttlSecs): Promise<number>` — Redis INCR atômico + EXPIRE na primeira chamada

### Fase 3 — TelegramGroupPublisher

**Criado** `telegram-groups/telegram-group-publisher.service.ts`:
- `publish(input)` → `{ queued, skipped, rateLimited }` — não faz I/O de rede, apenas enfileira
- Fluxo: selectEligibleGroups → rateLimiter.check → queue.add com jobId dedup
- `getQueueDepth()` — saúde da fila para health checks
- `jobId = tg-group:<groupId>:<messageHash>` — dedup no nível BullMQ

### Fase 3 — TelegramGroupProcessor

**Criado** `telegram-groups/telegram-group.processor.ts`:
- `@Processor(TELEGRAM_GROUP_QUEUE)` extends `WorkerHost`
- Double-check rate limit no processor (proteção contra jobs acumulados)
- Formato HTML personalizado com emoji por score (🔥 ≥90, ✨ ≥75, 💰 resto)
- Falha por rate limit → descarta sem retry (skip semântico)
- Falha por Telegram API → re-lança para BullMQ retry (2 tentativas)
- Registra sent/failed no DB + incrementa `tgGroupPostsTotal{group_name, status}`

### Fase 3 — TelegramGroupsModule

**Criado** `telegram-groups/telegram-groups.module.ts`:
- Imports: PrismaModule, RedisCacheModule, NotificationsModule, BullModule
- Providers: TelegramGroupsService, TelegramGroupRateLimiter, TelegramGroupPublisher, TelegramGroupProcessor
- Exports: TelegramGroupsService, TelegramGroupPublisher

**Complementado** `app.module.ts`:
- TelegramGroupsModule registrado na seção Integrations

### Fase 5 — MetricsService

**Complementado** `metrics/metrics.service.ts`:
- `tgGroupPostsTotal: Counter` → `poupi_tg_group_posts_total{group_name, status}`

### Fase 6 — Grafana Dashboard

**Complementado** `grafana/provisioning/dashboards/poupi_baby.json`:
- **+5 painéis** (total: 19 painéis):

| ID | Painel | Tipo | Métrica |
|---|---|---|---|
| 200 | Row: Telegram Group Distribution | row | — |
| 15 | Posts por grupo (sent/failed/rate_limited) | timeseries | poupi_tg_group_posts_total |
| 16 | Posts Falhados por Grupo (1h) | stat (colorido) | poupi_tg_group_posts_total{status="failed"} |
| 17 | Posts Bloqueados por Rate Limit (1h) | stat | poupi_tg_group_posts_total{status="rate_limited"} |
| 18 | Taxa de Sucesso por Grupo (24h) | timeseries | rate sent / total |
| 19 | Volume Diário por Grupo (24h) | barchart | increase sent 24h |

---

## TRILHA B — CRYPTO RESEARCH QA

### Fase 7 — ExperimentQA

**Criado** `research/experiment_qa.py`:

**Validações**:
1. Completeness — `REQUIRED_FIELDS` + `REQUIRED_METRICS` (sharpe, max_drawdown, total_trades)
2. Plausibilidade — `METRIC_BOUNDS`: sharpe [-10, 50], sortino [-20, 100], calmar [-10, 200], drawdown [-100, 0], win_rate [0, 1]
3. NaN/Infinito → error
4. Fora de range → warning
5. Parameter consistency vs StrategyRegistry canônico (warning se mismatch de tipo ou ausência)
6. Reproducibility — candles_count ausente (warning), replay_dataset ausente (info)
7. Duplicate run_id → error
8. Experimentos idênticos (sha256 de params+symbol+tf) → warning

**QAReport**:
- `quality_score` 0–100 (penaliza erros 5pt, warnings 1pt, normalizado por registros)
- `summary()` texto + `to_dict()` JSON

**CLI**: `--strategy`, `--all`, `--json`

### Fase 9 — StrategyRanker

**Criado** `research/strategy_ranker.py`:

**Score composto (0–100)**:
| Componente | Peso | Range normalização |
|---|---|---|
| Sharpe Ratio | 30% | [0, 5] |
| Sortino Ratio | 20% | [0, 10] |
| Calmar Ratio | 20% | [0, 5] |
| Max Drawdown | 15% | [-80%, 0%] |
| Expectancy | 10% | [0, 200] |
| Consistência | 5% | % experimentos sharpe > 0 |

**`StrategyRanker.rank()`**:
- Filtros: symbol, timeframe, strategy_ids, top_n, min_experiments
- Seleciona melhor experimento por Sharpe como baseline por estratégia
- `format_table()` — tabela ASCII com todas as métricas
- `to_dict()` — JSON com score_breakdown por componente

**CLI**: `--top`, `--symbol`, `--tf`, `--min-exp`, `--compare`, `--json`

### Fase 10 — DatasetQA

**Criado** `analytics/dataset_qa.py`:

**`run_dataset_qa(db, symbol, timeframe, days, source)`**:
- Usa `check_integrity()` / `check_all_symbols()` — sem duplicação
- Converte OHLCVIntegrityReport → `DatasetQAEntry` com classificação:
  - CLEAN: score ≥ 95
  - ACCEPTABLE: score ≥ 80
  - DEGRADED: score ≥ 60
  - CRITICAL: score < 60

**`DatasetQASummary`**:
- total_pairs, avg_score, median_score
- Contagem por classe (CLEAN/ACCEPTABLE/DEGRADED/CRITICAL)
- `critical_pairs` / `degraded_pairs` properties para priorização
- `quality_ranking(n)` — tabela dos N piores pares
- `to_dict()` JSON

**CLI**: `--all`, `--symbol/--tf`, `--critical-only`, `--ranking N`, `--json`, `--days`

---

## Fase 13 — Documentação

| Arquivo | Conteúdo |
|---|---|
| `data-core/ai/reports/PHASE_I_REPORT.md` | Este arquivo |
| `data-core/ai/contexts/research_behavior_status.md` | Atualizado |
| `poupi-baby/ai/contexts/current_status.md` | Atualizado |

---

## Critérios de Sucesso

| Critério | Status |
|---|---|
| Trilha A: TelegramGroup + TelegramGroupPost models Prisma | ✅ |
| Trilha A: TELEGRAM_GROUP_QUEUE + TelegramGroupJobData em queue.constants | ✅ |
| Trilha A: TelegramGroupRateLimiter — daily counter + interval key Redis | ✅ |
| Trilha A: CacheService.increment() — Redis INCR atômico com TTL | ✅ |
| Trilha A: TelegramGroupsService — CRUD + selectEligibleGroups + recordPost | ✅ |
| Trilha A: TelegramGroupPublisher — enfileira sem I/O de rede | ✅ |
| Trilha A: TelegramGroupProcessor — double-check rate limit, skip vs retry semânticos | ✅ |
| Trilha A: TelegramGroupsModule registrado em app.module.ts | ✅ |
| Trilha A: tgGroupPostsTotal counter no MetricsService | ✅ |
| Trilha A: 5 painéis Grafana adicionais (total: 19) | ✅ |
| Trilha B: ExperimentQA com 7 categorias de validação | ✅ |
| Trilha B: StrategyRanker com score composto 6 componentes | ✅ |
| Trilha B: DatasetQA fleet-wide com 4 classes de qualidade | ✅ |
| SEM duplicação de TelegramService, TelegramPost, NOTIFICATION_QUEUE | ✅ |

---

## Gaps Remanescentes (pós-Phase I)

| ID | Gap | Domínio | Prioridade |
|---|---|---|---|
| I-I-01 | Seed de grupos reais (script precisa ser criado + executado) | poupi-baby | Alta |
| I-I-02 | TelegramGroupPublisher não está sendo chamado por nenhum trigger ainda | poupi-baby | Alta |
| I-I-03 | Endpoint admin para criar/listar grupos (GET/POST /admin/telegram-groups) | poupi-baby | Média |
| I-I-04 | DealScoreService não chama publisher automaticamente após score alto | poupi-baby | Média |
| I-I-05 | ExperimentQA não integrado ao CI/scheduler (só via CLI) | crypto | Baixa |
| I-I-06 | DatasetQA não agendado (requer cron) | crypto | Baixa |
| H-H-02 | Token de tracking não embutido nos templates de email (persiste) | notificações | Alta |
| H-H-07 | BehaviorTrackingService não integrado aos controllers (persiste) | poupi-baby | Média |

---

*Phase I complete — Telegram Group Distribution & Crypto Research QA*
