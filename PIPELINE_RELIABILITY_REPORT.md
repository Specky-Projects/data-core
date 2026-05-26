# Pipeline Reliability Report

**Generated:** 2026-05-25  
**Phase:** PIPELINE RELIABILITY & SELF-HEALING  
**Status:** IMPLEMENTED

---

## Root Cause (Resolved)

| Finding | Detail |
|---------|--------|
| **Symptom** | `feed.count24h = 0` in `/readiness/price-intelligence` |
| **Root cause** | `SCHEDULER_PIPELINE_ENABLED=false` in `.env.example` → `normalize_job` never scheduled |
| **Effect** | `raw_collections` accumulated `normalization_pending`; `normalized_products` remained empty; `/price-feed` returned `count=0` permanently |
| **Fix** | Changed `.env.example` to `SCHEDULER_PIPELINE_ENABLED=true` with explanatory comments |
| **Secondary fix** | `health.service.ts` feed status semantics corrected: `ok / degraded / critical` (three-way distinction) |

---

## What Was Silent Before

1. `SCHEDULER_PIPELINE_ENABLED=false` produced **no error** — container was UP, scheduler was UP, jobs appeared registered, but `normalize_job` was simply never added to the schedule
2. `feed.count24h=0` was classified as `critical` (same as infra down) — no distinction between **pipeline stalled** vs **data-core unreachable**
3. No pipeline liveness tracking — impossible to know which pipelines were running vs stalled
4. No scheduler proof-of-execution — container alive ≠ jobs executing
5. No env drift detection — `.env.example` misconfiguration could propagate silently to production

---

## Implemented Components

### Phase 1 — Pipeline Liveness Registry
**File:** `app/pipeline/liveness.py`

Classifies 10 registered pipelines into explicit states:

| Status | Meaning |
|--------|---------|
| `RUNNING` | Run currently in-flight (started within 30 min) |
| `DEGRADED` | Last success within 2× expected interval (late but functional) |
| `STALLED` | Last success within 10× expected interval (significantly overdue) |
| `BLOCKED` | Last run errored, no success since |
| `DEAD` | No success in > 10× expected interval |
| `UNKNOWN` | No pipeline_runs records found |

Registered pipelines: `normalize_ecommerce`, `analytics_ecommerce`, `collection_ecommerce`, `normalize_crypto`, `analytics_crypto`, `collection_crypto`, `collection_real_estate`, `normalize_real_estate`, `normalize_trading`, `analytics_trading`

Cache: `runtime-data/pipeline_liveness.json` (atomic write, API reads without DB)

### Phase 2 — Scheduler Heartbeat Hardening
**Files:** `app/runtime/scheduler_heartbeat.py`, `scheduler/service.py`, `scheduler/jobs.py`

- `boot_heartbeat()` — records `scheduler_started_at` once at scheduler boot
- `record_job_execution()` — called after every `normalize_job` and `analytics_job` run
- `scheduler_heartbeat_job` — dedicated 5-minute proof-of-execution job
- `_with_heartbeat()` wrapper in `service.py` — non-invasively wraps pipeline jobs
- Cache: `runtime-data/scheduler_heartbeat.json`

Heartbeat age thresholds:
- `ALIVE`: age ≤ 10 min
- `STALLED`: age 10–30 min
- `DEAD`: age > 30 min

### Phase 3 — Dead Pipeline Detection
**File:** `app/pipeline/self_healing.py` (`DeadPipelineDetector`)

Detects four signal types:
1. `backlog_growing_normalize_static` — pending raws > 50 AND no normalization in > 20 min
2. `normalize_never_succeeded` — runs exist but no success/partial
3. `scheduler_heartbeat_stale` — heartbeat file > 10 min old
4. `pipeline_stalled` — derived from PipelineLivenessService (STALLED/DEAD/BLOCKED)

### Phase 4 — Queue Lag Intelligence
**Files:** `api/metrics.py` (new gauges)

New Prometheus metrics:
- `queue_backlog_total{module}` — pending normalization count
- `queue_lag_seconds{module}` — age of oldest pending raw
- `queue_oldest_job_age_seconds{module}` — age of oldest raw (any status)

### Phase 5 — Self-Healing Safe Recovery
**File:** `app/pipeline/self_healing.py` (`SelfHealingCoordinator`)

**NEVER performs:** delete, truncate, force cleanup, mass retry, automatic restart.

Allowed actions:
- `normalize_wake_up` — advisory: schedule a single bounded normalize run
- `log_only` — record signal for human review
- `throttled` — suppressed (> 3 triggers/hour per pipeline)

Rate limit: MAX_TRIGGERS_PER_HOUR = 3 per pipeline

Audit log: `runtime-data/self_healing_log.jsonl` (append-only)

### Phase 6 — Backlog Recovery Engine
**File:** `app/pipeline/self_healing.py` (`BacklogRecoveryEngine`)

Adaptive batch sizes based on DB pool pressure:
- DB pressure ≥ 90%: batch = 10 (minimum)
- DB pressure ≥ 70%: batch = base/2
- Backlog > 500: batch = base (clear faster)
- Backlog > 100: batch = 75% of base
- Normal: batch = min(base, 50)

### Phase 7 — Env Drift Detection
**File:** `scripts/audit_runtime_env.py`

Detects:
- `SCHEDULER_PIPELINE_ENABLED=false` → CRITICAL
- `SCHEDULER_ENABLED=false` → CRITICAL
- `DATABASE_URL` = dev default → CRITICAL
- `SCHEDULER_COLLECTORS_ENABLED=false` → WARNING
- `API_KEY=change-me` → WARNING

Exit codes: 0 = clean, 1 = critical, 2 = warnings

### Phase 8 — Operational Truth Metrics
**File:** `api/metrics.py` (appended)

New Prometheus gauges/counters:
- `pipeline_liveness_status{pipeline_id}` — 5=RUNNING, 4=DEGRADED, 3=STALLED, 2=BLOCKED, 1=DEAD, 0=UNKNOWN
- `pipeline_liveness_lag_seconds{pipeline_id}`
- `scheduler_heartbeat_age_seconds`
- `scheduler_consecutive_failures`
- `scheduler_execution_drift_seconds`
- `queue_backlog_total{module}`
- `queue_lag_seconds{module}`
- `self_healing_trigger_total{pipeline_id, action}`
- `self_healing_throttled_total{pipeline_id}`
- `dead_pipeline_signals_total{signal, severity}`

### Phase 9 — /system-status Expansion
**File:** `app/system_status.py`

New sections in response:
- `runtime.scheduler.heartbeat` — proof-of-execution heartbeat
- `pipelines` — full liveness snapshot from registry
- `queues.normalization_backlog` — queue lag summary

New blockers detected:
- `scheduler_heartbeat_dead`
- `pipeline_liveness_dead`
- `pipeline_liveness_blocked` (degraded)
- `pipeline_liveness_stalled` (degraded)

### Phase 10 — Grafana Dashboards
**Directory:** `grafana/dashboards/`

| Dashboard | UID | Purpose |
|-----------|-----|---------|
| Pipeline Liveness | `pipeline-liveness` | Status per pipeline, lag, backlog |
| Scheduler Reliability | `scheduler-reliability` | Heartbeat age, drift, protection mode |
| Queue Lag Intelligence | `queue-lag` | Backlog by module, oldest pending |
| Backlog Recovery | `backlog-recovery` | Recovery rate, self-healing activity |
| Self-Healing Activity | `self-healing` | Triggers, throttled, circuit breakers |
| Runtime Drift | `runtime-drift` | Execution drift, memory growth |
| Pipeline Freshness | `pipeline-freshness` | Normalization/analytics age per module |

### Phase 11 — Prometheus Alert Rules
**File:** `prometheus/rules/pipeline_reliability_alerts.yml`

| Alert | Severity | Threshold |
|-------|----------|-----------|
| `PipelineDead` | critical | `pipeline_liveness_status == 1` for 5m |
| `PipelineBlocked` | warning | `pipeline_liveness_status == 2` for 10m |
| `PipelineStalled` | warning | `pipeline_liveness_status == 3` for 15m |
| `NormalizationLagCritical` | critical | ecommerce lag > 2h |
| `AnalyticsLagCritical` | warning | ecommerce analytics lag > 4h |
| `SchedulerHeartbeatMissing` | critical | age > 10 min for 2m |
| `SchedulerConsecutiveFailures` | warning | ≥ 3 consecutive |
| `SchedulerExecutionDrift` | warning | > 5 min drift for 5m |
| `QueueBacklogExploding` | critical | ecommerce > 500 for 10m |
| `QueueBacklogElevated` | warning | ecommerce > 50 for 20m |
| `QueueOldestJobAgeCritical` | critical | oldest pending > 4h |
| `SelfHealingThrottleLoop` | warning | > 5 throttled in 30m |

### Phase 12 — Soak Reliability Tests
**File:** `scripts/soak_reliability_test.py`

Observes (no data modification):
- Scheduler heartbeat freshness per tick
- Pipeline liveness state
- Self-healing audit activity
- Consecutive failures

```bash
python scripts/soak_reliability_test.py --hours 6
python scripts/soak_reliability_test.py --hours 24 --interval 600
python scripts/soak_reliability_test.py --dry-run  # single pass
```

---

## Remaining Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Coolify overwrites env vars on deploy | High | `audit_runtime_env.py` should run pre-deploy |
| Single scheduler container (SPOF) | Medium | Phase 2 heartbeat detects stall within 10 min |
| Liveness cache staleness if scheduler down | Low | `/system-status` falls back to live DB eval |
| `PipelineRun` table growth over time | Low | `cleanup_stale_runs_job` runs every 15 min |

---

## Go/No-Go Criteria

| Criterion | Status |
|-----------|--------|
| Pipelines have explicit state | ✅ PASS |
| Scheduler heartbeat is proof-of-execution | ✅ PASS |
| Queue lag is observable | ✅ PASS |
| Backlog is trackable | ✅ PASS |
| Dead pipelines are detected | ✅ PASS |
| Stale pipelines are detected | ✅ PASS |
| Env drift is detectable | ✅ PASS |
| Self-healing is safe (no destructive actions) | ✅ PASS |
| Dashboards exist | ✅ PASS |
| Alerts exist | ✅ PASS |
| Runtime stable (no business logic changed) | ✅ PASS |

**Verdict: READY** (with soak validation pending production observation)
