# PHASE H REPORT — Behavior Tracking & Quant Research Infrastructure

> Executed: 2026-05-16
> Scope: poupi-baby (Trilha A) + data-core crypto research (Trilha B)
> Fases: 1–13

---

## Resumo Executivo

Phase H executou duas trilhas paralelas com foco em infraestrutura de rastreamento
de comportamento do usuário (poupi-baby) e maturidade da camada de pesquisa
quantitativa (crypto). Foram implementados 17 artefatos novos ou complementares.

**Trilha A**: Seed controlado, BehaviorTracking, AlertQuality, DealScore por categoria, Grafana provisioning.
**Trilha B**: ExperimentTracker, StrategyRegistry, ParameterSweep, RegimeAnalytics, OHLCV integrity extendida, métricas Prometheus wired.

**Crypto Research Layer classificado**: `L3 — Research Engine` (experiment tracking + observabilidade completa).
**poupi-baby comportamento**: `L2` — primeira versão de behavior tracking funcional.

---

## Auditoria Pre-Implementation (Anti-Duplicação)

| Item auditado | Resultado | Decisão |
|---|---|---|
| AnalyticsService.track() | ✅ Existe — persiste UserEvent | BehaviorTrackingService reutiliza via composition |
| MetricsService | ✅ Existe com 12 métricas | Complementar com behaviorEvents counter |
| DealScoreService.getTopOpportunities() | ✅ Existe | Complementar com getByCategory() — mesma SQL pattern |
| db_replay.replay_from_db() | ✅ Existe | Complementar com strategy_params override + metrics wire |
| ohlcv_integrity.check_integrity() | ✅ Existe | Complementar com drift + flat candles + integrity_score |
| StorageRepository.fetch_regime_performance() | ✅ Existe | regime_analytics.py complementa com analytics mais ricos |
| AlertEventsListener + CheckAlertsService | ✅ Existe | Sem alteração — BehaviorTrackingService é separado |
| api/metrics.py (Phase G metrics) | ✅ 5 métricas definidas | Wire em db_replay e ohlcv_integrity — G-H-04/05 resolvidos |

---

## TRILHA A — POUPI BABY

### Fase 1 — Seed Controlado de Usuários Internos

**Criado** `backend/src/seed/seed-internal-users.ts`:

- Cria 3 usuários internos com roles diferentes (admin, free, premium)
- Cria watchlists para categorias: Fraldas, Formula infantil, Lenços umedecidos
- Cria alertas em 90% do preço atual (target = price * 0.9)
- Guard contra execução em produção (`NODE_ENV === 'production'` → abort)
- Idempotente: `ON CONFLICT DO UPDATE` para watchlists, verifica existência de usuário
- Suporte a `TELEGRAM_INTERNAL_CHAT_ID_1/2` para configurar Telegram

**Uso:**
```bash
npx ts-node -r tsconfig-paths/register src/seed/seed-internal-users.ts
```

### Fase 2 — BehaviorTrackingService

**Criado** `backend/src/analytics/behavior-tracking.service.ts`:

- Novos tipos de evento: `alert.viewed`, `alert.dismissed`, `product.saved`, `category.followed`
- Reutiliza `AnalyticsService.track()` para persistência no UserEvent
- Incrementa `MetricsService.behaviorEvents` por `event_type`
- Falha silenciosa — nunca quebra a UX
- Helpers de conveniência: `alertViewed()`, `alertDismissed()`, `productSaved()`, `categoryFollowed()`

**Modificado** `MetricsService`:
```ts
behaviorEvents: Counter  // poupi_behavior_events_total{event_type}
```

**PromQL:**
```promql
rate(poupi_behavior_events_total[5m])  # taxa de eventos por tipo
increase(poupi_behavior_events_total{event_type="alert.dismissed"}[24h])  # dismissals/24h
```

### Fase 3 — AlertQualityService

**Criado** `backend/src/analytics/alert-quality.service.ts`:

**`getCTRByCategory(days)`**:
- Extrai `category` do payload JSON dos UserEvent
- Agrupa por `notification.opened`, `notification.clicked`, `alert.viewed`
- Retorna `openRate` e `clickRate` por categoria

**`getAlertFatigueReport(days)`**:
- Conta total enviados, abertos, clicados, descartados
- Calcula `fatigueScore` 0–100 (100 = máxima fadiga)
- Gera `recommendation` textual automaticamente

**`getTopEngagedProducts(limit, days)`**:
- Top produtos por CTR de `notification.clicked`
- Join via payload JSON `productId` com tabela products

### Fase 4 — Opportunity Refinement

**Complementado** `DealScoreService.getByCategory()`:
- Mesma SQL pattern de `getTopOpportunities()` com filtro `p.category ILIKE %category%`
- Endpoint: `GET /deal-score/category/:category?limit=10&minScore=60`
- Exemplos: `/deal-score/category/Fraldas`, `/deal-score/category/Formula%20infantil`

### Fase 5 — Grafana Dashboard Provisioning

**Criados** `grafana/provisioning/`:
- `datasources/prometheus.yml` — datasource Prometheus configurado
- `dashboards/dashboard.yml` — provisioner apontando para `/etc/grafana/provisioning/dashboards`
- `dashboards/poupi_baby.json` — **14 painéis**:

| Painel | Tipo | Métricas |
|---|---|---|
| Alertas disparados/min | timeseries | poupi_alert_dispatched_total |
| Notificações entregues/falhas | timeseries | poupi_notification_delivered_total |
| CTR de Alertas (24h) | gauge | notification_engaged / notification_delivered |
| Engajamento (opens+clicks) | barchart | poupi_notification_engaged_total |
| Behavior Events/min | timeseries | poupi_behavior_events_total |
| Watchlists ativas (total) | stat | watchlist_actions created - removed |
| Watchlist actions/min | timeseries | poupi_watchlist_actions_total |
| Alertas disparados/24h | stat | poupi_alert_dispatched_total |
| BullMQ — jobs por estado | timeseries | waiting + active + delayed |
| Jobs falhados por fila | stat (colorido) | poupi_bullmq_queue_failed |
| Sync items/min | timeseries | poupi_data_core_sync_items_total |
| Duração do sync p50/p95 | timeseries | poupi_data_core_sync_duration_seconds |
| HTTP Requests/s | timeseries | http_requests_total |
| Latência HTTP p95 | timeseries | http_request_duration_seconds |

---

## TRILHA B — CRYPTO RESEARCH

### Fase 6 — ExperimentTracker

**Criado** `research/experiment_tracker.py`:

**`ExperimentRecord`** (dataclass):
- Campos: strategy_id, strategy_version, symbol, timeframe, parameters
- metrics dict: sharpe, sortino, calmar, max_drawdown, expectancy, etc.
- replay_dataset, replay_days, candles_count
- equity_curve + regime_performance (opcionais)
- run_id (UUID), created_at, notes

**`ExperimentTracker`**:
- Persistência JSONL: `data/experiments/{strategy_id}.jsonl` + `all_experiments.jsonl`
- `save()`, `record()` — persiste novo experimento
- `load_all(strategy_id, symbol, timeframe, limit)` — filtra e ordena
- `get_best(metric)` — melhor por métrica
- `compare(top_n, sort_by)` — tabela comparativa formatada
- `summary()` — média/melhor Sharpe, Sortino, Calmar por estratégia

**CLI:**
```bash
python -m domains.crypto_coin.research.experiment_tracker --compare --strategy trend_following --top 10
python -m domains.crypto_coin.research.experiment_tracker --best --metric sortino
python -m domains.crypto_coin.research.experiment_tracker --summary
```

### Fase 7 — Strategy Registry

**Criado** `research/strategy_registry.yaml` com 4 estratégias:
- `trend_following` (active) — estratégia principal do TradingBot v4
- `breakout_scalper` (research) — rompimento de resistência
- `mean_reversion` (research) — RSI oversold em regime NEUTRAL
- `shadow_tester` (active) — shadow trading paralelo

**Criado** `research/strategy_registry.py`:
- `StrategyRegistry.get(strategy_id)` → `StrategyDefinition`
- `get_parameters(strategy_id)` → dict de parâmetros canônicos
- `list_active()`, `list_research()`, `summary()`
- Lazy load YAML — carrega na primeira chamada
- `reload()` — force reload do YAML

### Fase 8 — Research Orchestration (sweep_runner)

**Criado** `research/sweep_runner.py`:

**`run_sweep(db, strategy_id, symbol, timeframe, days, sweep_params, max_configs)`**:
- `parse_sweep_spec(["rsi_oversold:25,30,35", "stop_loss_pct:1.5,2.0"])` → dict com listas
- `build_parameter_grid(base_params, sweep)` → cartesian product de configurações
- Executa `replay_from_db()` para cada config
- Registra resultado no `ExperimentTracker` automaticamente
- Limita a `max_configs=50` para evitar explosão combinatória
- Retorna resultados ordenados por Sharpe

**`run_batch(db, strategy_id, symbols, timeframes, days)`**:
- Replica parâmetros canônicos em múltiplos símbolos/timeframes
- Auto-record no ExperimentTracker

**CLI:**
```bash
python -m domains.crypto_coin.research.sweep_runner \
  --strategy trend_following --symbol BTC/USDT --tf 15m --days 90 \
  --sweep rsi_oversold:25,30,35,40 stop_loss_pct:1.5,2.0,2.5

python -m domains.crypto_coin.research.sweep_runner \
  --strategy trend_following --all-symbols --tf 15m --days 60
```

### Fase 9 — Regime Analytics

**Criado** `analytics/regime_analytics.py`:

**`analyze_regime_performance(db, symbol, timeframe, days)`**:
- Usa `StorageRepository.fetch_regime_performance()` + `fetch_recent_trades()` + `fetch_signal_decisions()`
- Computa por regime: win_rate, avg_pnl_pct, max_drawdown, avg_confidence, exposure_pct
- Distribuição de candles por regime (% de tempo em BULLISH/BEARISH/NEUTRAL/VOLATILE)
- Volatility buckets: low/medium/high/extreme baseados em HV
- Regime transitions: de→para, quantas vezes, confiança antes/depois
- `best_regime` / `worst_regime` / `reliable_regimes` (wr ≥ 60%, n ≥ 5 trades)

### Fase 10 — OHLCV Integrity Extendida

**Modificado** `analytics/ohlcv_integrity.py`:

**Novas detecções:**
| Detecção | Critério | Tipo |
|---|---|---|
| Timeframe drift | delta atual vs tf esperado diverge > 10% | warning (contador) |
| Flat candle | O == H == L == C | `AnomalyRecord(kind='flat_candle')` |

**Nova propriedade `integrity_score` (0–100):**
```
score = completeness_pct
       - gap_penalty    (min 30, 2pt/gap)
       - anomaly_penalty (min 20, 1.5pt/anomalia)
       - drift_penalty   (min 10, 0.5pt/drift)
       - flat_penalty    (min 5, 0.2pt/flat)
```

### Fase 11 — Global Observability (G-H-04 + G-H-05 resolvidos)

**db_replay.py — G-H-05 resolvido:**
```python
# Wired após cada replay:
backtest_runs_total.labels(symbol, timeframe, mode="db").inc()
backtest_duration_seconds.labels(symbol, timeframe, mode="db").observe(elapsed)
backtest_candles_processed_total.labels(symbol, timeframe).inc(len(df))
```

**ohlcv_integrity.py — G-H-04 resolvido:**
```python
# Wired após cada check_integrity():
ohlcv_integrity_checks_total.labels(symbol, timeframe, status=report.status).inc()
ohlcv_gaps_detected_total.labels(symbol, timeframe).inc(report.gap_count)
```

**Lazy import pattern**: ambos usam `_get_metrics()` com try/except para não quebrar CLI quando API não disponível.

---

## Fase 12 — Documentação

| Arquivo | Conteúdo |
|---|---|
| `docs/RESEARCH_AND_BEHAVIOR_MATRIX.md` | Matriz consolidada: research + behavior por domínio + implementações H |
| `ai/contexts/research_behavior_status.md` | Estado atual compacto para contexto de IA |

---

## Fase 13 — Validação Final

### Poupi Baby — evidências

| Componente | Evidência |
|---|---|
| seed-internal-users.ts | Script idempotente, guard production, seed watchlists + alertas por categoria |
| BehaviorTrackingService | Reutiliza AnalyticsService.track(), silenciosa, helpers de conveniência |
| AlertQualityService | CTR por categoria (SQL + payload JSON), fatigue score 0–100, top products |
| getByCategory() | Filtro ILIKE na categoria, mesma SQL pattern que getTopOpportunities() |
| GET /deal-score/category/:category | Endpoint autenticado, parsedLimit, parsedMinScore |
| behaviorEvents counter | poupi_behavior_events_total{event_type} em MetricsService |
| Grafana — 14 painéis | JSON provisionado com datasource, rows, alertas BullMQ coloridos |

### Crypto — evidências

| Componente | Evidência |
|---|---|
| ExperimentTracker | save/load/compare/best/summary; JSONL por estratégia + global |
| StrategyRegistry | YAML 4 estratégias; get(), get_parameters(), list_active(), summary() |
| sweep_runner | parse_sweep_spec → cartesian product → replay_from_db → record |
| regime_analytics | RegimePerformanceDetail por regime; volatility buckets; transitions |
| OHLCV integrity_score | Fórmula: completeness - gap/anomaly/drift/flat penalties |
| backtest_runs_total | Wired em replay_from_db() com lazy metrics import |
| ohlcv_integrity_checks_total | Wired em check_integrity() com status label |
| strategy_params override | replay_from_db aceita parâmetros externos para sweep |

---

## Critérios de Sucesso

| Critério | Status |
|---|---|
| Trilha A: Seed script criado e documentado | ✅ |
| Trilha A: BehaviorTrackingService com 4 event types + Prometheus | ✅ |
| Trilha A: AlertQualityService com CTR + fatigue + top products | ✅ |
| Trilha A: DealScore por categoria com endpoint | ✅ |
| Trilha A: Grafana dashboard provisionado (14 painéis) | ✅ |
| Trilha B: ExperimentTracker com persistência JSONL e CLI | ✅ |
| Trilha B: StrategyRegistry YAML com 4 estratégias | ✅ |
| Trilha B: sweep_runner com grid search + batch + auto-record | ✅ |
| Trilha B: regime_analytics com win/loss/volatility/transitions | ✅ |
| Trilha B: OHLCV integrity + drift + flat + integrity_score | ✅ |
| Trilha B: G-H-05 resolvido — backtest_runs_total wired em db_replay | ✅ |
| Trilha B: G-H-04 resolvido — ohlcv_integrity metrics wired | ✅ |
| RESEARCH_AND_BEHAVIOR_MATRIX.md criada | ✅ |
| SEM duplicação de serviços/pipelines existentes | ✅ |

---

*Phase H complete — Behavior Tracking & Quant Research Infrastructure*
