# Self-Healing Architecture

**Phase:** PIPELINE RELIABILITY & SELF-HEALING  
**Date:** 2026-05-25  
**Status:** IMPLEMENTED — observe-only, no destructive automation

---

## Design Philosophy

The self-healing system is built on three non-negotiable constraints:

1. **No destructive automation** — deletes, truncates, force cleanups, and mass retries are permanently forbidden at the code level
2. **Bounded recovery** — every action has a hard rate limit (≤ 3 per pipeline per hour)
3. **Advisory-first** — the system detects and logs; it recommends actions, it does not execute jobs autonomously

The goal is **visibility before intervention**: operators must never be surprised by a stalled pipeline they didn't know about. Automated recovery is a secondary concern — honest detection comes first.

---

## Component Map

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Scheduler Process                               │
│                                                                        │
│  APScheduler                                                           │
│  ├─ normalize_job        ──→ _with_heartbeat("normalize_job") ─────┐   │
│  ├─ analytics_job        ──→ _with_heartbeat("analytics_job")  ─┐  │   │
│  ├─ scheduler_heartbeat_job (every 5 min)                        │  │   │
│  └─ ... other jobs                                               │  │   │
│                                                                  ▼  ▼   │
│                                               record_job_execution()    │
│                                                        │               │
└────────────────────────────────────────────────────────│───────────────┘
                                                         │
                                              runtime-data/ volume
                                                         │
                              ┌──────────────────────────▼─────────────────┐
                              │         runtime-data/                       │
                              │  scheduler_heartbeat.json  ←── written by   │
                              │  pipeline_liveness.json    ←── scheduler /  │
                              │  self_healing_log.jsonl    ←── API process  │
                              │  self_healing_state.json                    │
                              │  scheduler_watchdog_snapshot.json           │
                              └─────────────────────┬──────────────────────┘
                                                    │
                              ┌─────────────────────▼──────────────────────┐
                              │              API Process                    │
                              │                                             │
                              │  /system-status                             │
                              │   ├─ _scheduler_heartbeat_status()  ←file  │
                              │   └─ _pipeline_liveness_status()    ←file  │
                              │                                             │
                              │  /metrics  ←── set_function() gauges       │
                              │   ├─ pipeline_liveness_status{pid}          │
                              │   ├─ scheduler_heartbeat_age_seconds        │
                              │   └─ queue_backlog_total{module}  ←── DB   │
                              └─────────────────────────────────────────────┘
```

---

## Liveness Model

### State Machine

```
          ┌─────────────┐
          │   UNKNOWN   │  ← no pipeline_runs records ever
          └──────┬──────┘
                 │ first run created
                 ▼
          ┌─────────────┐
          │   RUNNING   │  ← run.status='running', started < 30 min ago
          └──────┬──────┘
                 │ run finishes
         ┌───────┴──────────┐
         │                  │
         ▼                  ▼
   ┌──────────┐       ┌──────────┐
   │ DEGRADED │       │ BLOCKED  │
   │(lag ≤ 2×)│       │(errors,  │
   │          │       │ no succ) │
   └────┬─────┘       └────┬─────┘
        │ lag > 2× expected │ lag > dead_threshold
        ▼                  ▼
   ┌──────────┐       ┌──────────┐
   │ STALLED  │       │   DEAD   │
   │(2×–10×)  │       │  (>10×)  │
   └──────────┘       └──────────┘
```

### Expected Intervals

| Pipeline | Domain | Stage | Expected Interval |
|----------|--------|-------|-------------------|
| `normalize_ecommerce` | ecommerce | normalization | 15 min |
| `analytics_ecommerce` | ecommerce | analytics | 60 min |
| `collection_ecommerce` | ecommerce | collection | 120 min |
| `normalize_crypto` | crypto | normalization | 15 min |
| `analytics_crypto` | crypto | analytics | 60 min |
| `collection_crypto` | crypto | collection | 60 min |
| `collection_real_estate` | real_estate | collection | 24 h |
| `normalize_real_estate` | real_estate | normalization | 24 h |
| `normalize_trading` | trading | normalization | 15 min |
| `analytics_trading` | trading | analytics | 60 min |

### DEGRADED threshold: 2× expected interval
### STALLED/BLOCKED threshold: 2×–10× expected interval
### DEAD threshold: > 10× expected interval

---

## Heartbeat Model

The scheduler heartbeat is a **proof-of-execution file**, not a process health check.

```
Scheduler process                runtime-data/scheduler_heartbeat.json
─────────────────                ────────────────────────────────────────
boot_heartbeat()        ────→    { scheduler_started_at, pid, written_at }
                                          │
normalize_job runs                        │
_with_heartbeat() wrapper ─────→ { last_job: "normalize_job",
                                   last_job_at: <now>,
                                   last_job_status: "success",
                                   last_job_duration_seconds: 1.23,
                                   consecutive_failures: 0,
                                   jobs_executed_total: 42,
                                   execution_drift_seconds: 8.1 }
                                          │
scheduler_heartbeat_job (5 min) ──→ { last_job: "scheduler_heartbeat_job",
                                      written_at: <now> }
```

**Freshness thresholds:**
- `ALIVE`: written_at age ≤ 10 min
- `STALLED`: age 10–30 min  
- `DEAD`: age > 30 min — scheduler may be frozen

**What container-UP does NOT prove:**
- That APScheduler is dispatching jobs
- That `normalize_job` is actually running
- That `SCHEDULER_PIPELINE_ENABLED=true` at runtime

---

## Dead Pipeline Detection

### Signal Types

```python
class DeadSignal(str, Enum):
    BACKLOG_GROWING_NORMALIZE_STATIC  # pending raws > 50 AND normalize > 20 min stale
    NORMALIZE_NEVER_SUCCEEDED          # runs exist, no success ever
    ANALYTICS_STALE                    # analytics lag > threshold
    SCHEDULER_HEARTBEAT_STALE          # heartbeat file > 10 min old
    PIPELINE_STALLED                   # derived from PipelineLivenessService
```

### Detection Flow

```
DeadPipelineDetector.detect()
├─ _check_backlog_vs_normalize()
│   ├─ query: raw_collections WHERE processing_status='normalization_pending' AND module='ecommerce'
│   └─ if count > 50 AND normalized_at older than 20 min → BACKLOG_GROWING_NORMALIZE_STATIC
│
├─ _check_scheduler_heartbeat()
│   ├─ read: runtime-data/scheduler_heartbeat.json
│   └─ if age > 10 min → SCHEDULER_HEARTBEAT_STALE
│
└─ _check_liveness_states()
    ├─ PipelineLivenessService(db).snapshot()
    └─ for each STALLED/DEAD/BLOCKED pipeline → PIPELINE_STALLED
```

---

## Queue Model

### Backlog Classification

```
raw_collections
├─ processing_status = 'normalization_pending'  ← backlog (want 0)
├─ processing_status = 'normalization_failed'   ← dead-letter (investigate)
├─ processing_status = 'normalized'             ← processed (good)
└─ processing_status = 'ignored'                ← dedup/skipped (expected)
```

### Backlog Recovery Batch Sizing

```
BacklogRecoveryEngine.compute_safe_batch_size(module, backlog_count)

DB pressure = pool.checkedout() / pool.size()

pressure ≥ 0.9 → batch = 10   (critical — minimum)
pressure ≥ 0.7 → batch = base/2  (high — halve)
backlog > 500  → batch = base     (large backlog — clear faster)
backlog > 100  → batch = base×0.75
else           → batch = min(base, 50)  (conservative default)
```

Where `base = settings.scheduler_reliability_base_batch_size` (default: 100).

---

## Self-Healing Decision Matrix

| Signal | Severity | Action | Throttled? |
|--------|----------|--------|-----------|
| `BACKLOG_GROWING_NORMALIZE_STATIC` | critical | `normalize_wake_up` (advisory) | Yes (3/h) |
| `SCHEDULER_HEARTBEAT_STALE` | warning/critical | `log_only` + human escalation | No |
| `PIPELINE_STALLED` (DEAD) | critical | `normalize_wake_up` (advisory) | Yes (3/h) |
| `PIPELINE_STALLED` (STALLED) | warning | `log_only` | No |
| `PIPELINE_STALLED` (BLOCKED) | warning | `log_only` | No |

### Throttle Logic

```python
MAX_TRIGGERS_PER_HOUR = 3  # per pipeline_id

_is_throttled(pipeline_id):
    now = utcnow()
    cutoff = now - 1h
    recent = [ts for ts in triggers[pipeline_id] if ts >= cutoff]
    return len(recent) >= MAX_TRIGGERS_PER_HOUR
```

The rate limiter prevents recovery loops. If `normalize_wake_up` is triggered 3× in 1 hour and the pipeline is still stalled, the 4th trigger is `throttled` — this is a `SelfHealingThrottleLoop` alert signal requiring human intervention.

### Audit Trail

Every decision (including throttled ones) is appended to `runtime-data/self_healing_log.jsonl`:

```json
{"action": "normalize_wake_up", "pipeline_id": "normalize_ecommerce",
 "triggered_by": "backlog_growing_normalize_static",
 "details": {"pending_raws": 947, "normalize_age_seconds": 1803},
 "timestamp": "2026-05-25T14:00:00Z"}
```

---

## Env Drift Model

The root cause of this entire phase was `SCHEDULER_PIPELINE_ENABLED=false` propagating silently to production.

### Critical Variables

| Variable | Dangerous Value | Effect |
|----------|-----------------|--------|
| `SCHEDULER_PIPELINE_ENABLED` | `false` | normalize_job + analytics_job never scheduled |
| `SCHEDULER_ENABLED` | `false` | ALL jobs disabled |
| `DATABASE_URL` | dev default | prod DB inaccessible |
| `SCHEDULER_COLLECTORS_ENABLED` | `false` | no new raw data |
| `SCHEDULER_DOMAIN_JOBS_ENABLED` | `false` | VTEX scraping disabled |

### Drift Detection

```bash
# Run before every deploy
python scripts/audit_runtime_env.py

# Exit 0 = clean, 1 = critical drift, 2 = warnings
```

The auditor compares runtime `os.environ` against:
1. Rules in `CRITICAL_RULES` (hardcoded known-dangerous values)
2. Keys present in `.env.example` but absent in runtime

---

## Runtime-Data Volume Layout

All reliability state is persisted to `runtime-data/` — a shared Docker volume between the `api` and `scheduler` containers. Files are written atomically (tmp → rename) to prevent partial reads.

```
runtime-data/
├─ scheduler_heartbeat.json          ← Phase 2: proof-of-execution
├─ pipeline_liveness.json            ← Phase 1: liveness registry cache
├─ self_healing_log.jsonl            ← Phase 5: append-only audit
├─ self_healing_state.json           ← Phase 5: throttle state
├─ scheduler_watchdog_snapshot.json  ← existing: memory/cgroup snapshot
├─ scheduler_watchdog_history.jsonl  ← existing: watchdog history
├─ scheduler_reliability_audit.jsonl ← existing: reliability engine
├─ worker_heartbeat.json             ← existing: worker heartbeat
└─ scheduler_lifecycle.jsonl         ← existing: lifecycle events
```

---

## Prometheus Metrics Reference (Phase 8)

| Metric | Labels | Source |
|--------|--------|--------|
| `pipeline_liveness_status` | `pipeline_id` | liveness cache file |
| `pipeline_liveness_lag_seconds` | `pipeline_id` | liveness cache file |
| `scheduler_heartbeat_age_seconds` | — | heartbeat file |
| `scheduler_consecutive_failures` | — | heartbeat file |
| `scheduler_execution_drift_seconds` | — | heartbeat file |
| `queue_backlog_total` | `module` | DB (at scrape time) |
| `queue_lag_seconds` | `module` | DB (at scrape time) |
| `queue_oldest_job_age_seconds` | `module` | DB (at scrape time) |
| `self_healing_trigger_total` | `pipeline_id`, `action` | counter (in-process) |
| `self_healing_throttled_total` | `pipeline_id` | counter (in-process) |
| `dead_pipeline_signals_total` | `signal`, `severity` | counter (in-process) |

---

## What Is NOT Automated

The following actions are **permanently prohibited** by design:

| Prohibited Action | Reason |
|-------------------|--------|
| `DELETE FROM raw_collections` | Data destruction — irreversible |
| `TRUNCATE normalized_products` | Business data loss |
| Mass retry without limit | Could overwhelm DB under pressure |
| Automatic container restart | Could mask root cause, cause restart loop |
| Force-close circuit breakers | Could re-trigger anti-bot blocks |
| Bulk `processing_status = 'normalization_pending'` reset | Could cause duplicate normalization |

All of these require explicit human authorization.

---

## Remaining Risks

| Risk | Severity | Current Mitigation | Gap |
|------|----------|--------------------|-----|
| Single scheduler container (SPOF) | Medium | Heartbeat detects stall in ≤ 10 min | No automatic failover |
| Coolify overwrites SCHEDULER_PIPELINE_ENABLED on deploy | High | `audit_runtime_env.py` pre-deploy check | Not automated in CI/CD pipeline |
| Pipeline liveness cache stale if scheduler crashes | Low | API falls back to live DB eval | Small window of stale data |
| Self-healing wake-up races with scheduler | Low | Rate limiter + idempotent normalize_job | No distributed lock |
| `pipeline_runs` table unbounded growth | Low | `cleanup_stale_runs_job` (15 min) | No size alerting |
