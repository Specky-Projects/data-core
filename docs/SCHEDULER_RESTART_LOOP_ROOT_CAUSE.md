# Scheduler Restart Loop Root Cause

Status: `NO-GO` for runtime protection enablement.

## Finding

The dominant `CRITICAL_PROTECTION` state was caused by an untrusted restart counter, not by proven container restarts.

The runtime snapshot observed during calibration contained:

- `observed_restart_count=3`
- no `restart_count_source`
- no `probe_boot_count`
- no `process_started_at`
- `memory_events.oom=0`
- `memory_events.oom_kill=0`
- `memory_limit_bytes=null`
- `swap_usage_bytes` near zero
- `trend_state=MEMORY_STABLE`

That shape matches legacy/probe-local evidence. The probe can count its own boots, but from inside the container it cannot prove Docker/container restarts. Treating that value as real restart-loop provenance made the reliability engine classify healthy/stable samples as `SCHEDULER_RESTART_LOOP`, which then mapped to `CRITICAL_PROTECTION` in dry-run.

## Causality

| Signal | Observation | Interpretation |
| --- | --- | --- |
| Restart count | `observed_restart_count=3` | Legacy/untrusted without source |
| OOM | `oom=0`, `oom_kill=0` | No cgroup OOM evidence |
| Memory | stable around cgroup RSS samples | No memory pressure causal chain |
| Swap | near zero and not persistently growing | No swap pressure causal chain |
| Backlog | `pending_total=0`, `backlog_score=0.0` in audit | No queue pressure causal chain |
| Mode | `CRITICAL_PROTECTION` predominant | Derived from false restart-loop classification |

## Mitigation Applied

The watchdog now separates:

- real restarts with explicit provenance: `docker`, `container_runtime`, `supervisor`, or `real_restart_count`
- false/legacy restart evidence: `observed_restart_count` without source
- probe-local boot count: `probe_boot_count`, never treated as real restart count

New diagnosis fields:

- `restart_reason_chain`
- `restart_provenance`
- `real_restart_count`
- `false_restart_count`
- `heartbeat_age_seconds`
- `watchdog_confidence_score`
- `execution_drift_seconds`
- `runtime_memory_pressure_score`
- `swap_growth_bytes`

If legacy restart evidence is present without real provenance, the watchdog now returns `OBSERVE_MORE` with low confidence instead of `SCHEDULER_RESTART_LOOP`.

## Metrics Added

- `scheduler_restart_loop_total`
- `scheduler_restart_real_total`
- `scheduler_false_restart_total`
- `scheduler_heartbeat_age_seconds`
- `scheduler_execution_drift_seconds`
- `runtime_memory_pressure_score`
- `runtime_swap_growth_bytes`
- `watchdog_confidence_score`

## Operational Decision Matrix

| Condition | Runtime Reliability |
| --- | --- |
| real restart provenance + repeated restarts | `BLOCKED` |
| stale heartbeat + no real restart provenance | `WARNING` |
| legacy restart count only | `WARNING`, observe more |
| swap high + drift low | `DEGRADED` |
| swap high + drift high | `BLOCKED` |
| OOM recent | `BLOCKED` |
| memory stable + no OOM + false restart count | `NO-GO` for enablement until refreshed, but not critical protection |
| heartbeat fresh + low pressure + no drift + no real restart | `READY` for calibration only |

## Remaining Risk

The scheduler was refreshed with the hardened probe on 2026-05-25 using an API+scheduler-only rebuild.

Post-deploy evidence:

- API image: `sha256:bde9b8252136b1e1205635744bed73a4ce7e2c7c31cfa222158f92fc97dd6727`
- Scheduler image: `sha256:69766607e9cc27be50d524b24b215b7064d9836555189a1c26d2fb4de98a2aff`
- `restart_count_source=probe_only`
- `observed_restart_count=0`
- `real_restart_count=0`
- `false_restart_count=0`
- `scheduler_restart_loop_total=0`
- `scheduler_restart_real_total=0`
- `scheduler_false_restart_total=0`
- `watchdog_confidence_score=0.8` to `0.9` in immediate samples
- `memory_events.oom=0`
- `memory_events.oom_kill=0`
- Docker scheduler restartCount remained `0`
- `scheduler_execution_drift.jsonl` is pending real APScheduler job completion under the new listener

The remaining risk is no longer ambiguous restart-loop classification. The current risk is insufficient post-deploy observation window plus runtime backlog pressure.

Do not enable `SCHEDULER_RELIABILITY_ENABLED` while `restart_provenance` is missing, `watchdog_confidence_score < 0.8`, or `scheduler_false_restart_total > 0`.

## Next Validation Window

Run a new dry-run observation after the scheduler runtime contains the hardened probe:

- 6h minimum
- 24 dry-run decisions minimum
- `scheduler_restart_real_total=0` unless explained by a real deployment event
- `scheduler_false_restart_total=0`
- `watchdog_confidence_score >= 0.8`
- `scheduler_execution_drift_seconds < 300`
- `runtime_memory_pressure_score < 0.75`
- no unexplained `PROTECTIVE` or `CRITICAL_PROTECTION`

### Passive checkpoint 2026-05-25T10:48Z

The post-deploy window is still insufficient: about 7 minutes, `0` dry-run decisions, and no `scheduler_execution_drift.jsonl` yet.

Healthy evidence so far:

- API and scheduler are Docker healthy.
- Docker restartCount remains `0`.
- OOM remains `0`.
- `restart_count_source=probe_only`.
- `observed_restart_count=0`.
- `scheduler_restart_loop_total=0`.
- `scheduler_restart_real_total=0`.
- `scheduler_false_restart_total=0`.
- `watchdog_confidence_score=0.8`.
- `/system-status` reports `DEGRADED` for real backlog/provider conditions, not restart-loop.

Runtime protection remains `NO-GO` until the 6h/24-decision gate is met.

### Extended checkpoint 2026-05-25T10:53Z

Additional passive evidence:

- API and scheduler remain healthy.
- Docker restartCount remains `0`.
- OOM remains `0`.
- `restart_count_source=probe_only`.
- `observed_restart_count=0`.
- `scheduler_restart_loop_total=0`.
- `scheduler_restart_real_total=0`.
- `scheduler_false_restart_total=0`.
- `runtime_swap_growth_bytes=0`.
- `watchdog_confidence_score=0.8`.
- A real APScheduler collection run completed: `crypto.crypto_coin_ohlcv`, status `success`, `raw_saved_count=120`.

Open issue:

- `scheduler_execution_drift.jsonl` was still missing after that completed job.
- The scheduler container contains the listener code, and logs did not show a drift write error.
- Scheduler forensics remains partially validated until drift persistence appears or the listener gap is explained.

Runtime protection remains `NO-GO`.

### 6h+ checkpoint 2026-05-25T18:17Z

The elapsed time gate was met at `7.6232` hours, but final validation remains `NO-GO`.

Evidence:

- Post-deploy dry-run decisions: `0`.
- Drift persistence is proven: `5` events in `scheduler_execution_drift.jsonl`.
- Max drift: `54.772003` seconds on `collector:crypto.crypto_coin_ohlcv`.
- Average drift: `19.1258026` seconds.
- Last restart provenance: `restart_count_source=probe_only`.
- `observed_restart_count=0`.
- `oom_kill_count=0`.
- `oom_recent=false`.
- `swap_usage_bytes=0`.

Failure condition:

- Last scheduler watchdog snapshot is stale: `24961.104` seconds old at checkpoint.
- Docker API is unavailable; the `dockerDesktopLinuxEngine` pipe is missing.
- `GET /health` and `localhost:8000` TCP checks failed.
- Live `/system-status` and `/metrics` could not be queried.

Decision:

- Watchdog observability: `NO-GO` for final 6h validation.
- Scheduler forensics: `PARTIAL`; drift is now emitted, but the continuous window did not remain observable.
- Runtime protection: `NO-GO`.
- Trading/live changes: `NO-GO`.

### Final checkpoint 2026-05-25T21:17Z

The extended observation reached `10.6238` hours, but final validation remains `NO-GO`.

Evidence:

- Post-deploy dry-run decisions: `0`.
- Drift events: `5`.
- Average drift: `19.1258026` seconds.
- Max drift: `54.772003` seconds.
- Jobs with drift evidence:
  - `collector:crypto.crypto_coin_ohlcv`: `2`.
  - `maintenance:cleanup_stale_runs`: `2`.
  - `platform:operational_watchdog`: `1`.
- Last snapshot source: `probe_only`.
- Last `observed_restart_count=0`.
- Last `oom_kill_count=0`.
- Last `oom_recent=false`.
- Last `swap_usage_bytes=0`.
- Last heartbeat snapshot stale by `9918.072` seconds.
- Docker API unavailable and API endpoints unreachable.

Final decision:

- Watchdog observability: `NO-GO`.
- Scheduler forensics: `PARTIAL`.
- Runtime protection: `NO-GO`.
- Trading/live changes: `NO-GO`.

### Final passive window checkpoint 2026-05-26T17:02Z

The preferred passive window exceeded 24 hours (`30.3722` hours since controlled deploy), but final validation remains `NO-GO`.

Evidence:

- Post-deploy dry-run decisions: `3`.
- Post-deploy decision modes: `NORMAL=3`.
- Drift events: `68`.
- Average drift: `8.634050411764704` seconds.
- Max drift: `54.772003` seconds.
- Jobs with drift evidence:
  - `platform:scheduler_heartbeat`: `33`.
  - `collector:crypto.crypto_coin_ohlcv`: `13`.
  - `maintenance:cleanup_stale_runs`: `13`.
  - `platform:operational_watchdog`: `6`.
  - `maintenance:alert_webhook`: `2`.
  - `ecommerce:url_scraper_targets`: `1`.
- Last snapshot source: `probe_only`.
- Last `observed_restart_count=0`.
- Last `oom_kill_count=0`.
- Last `swap_usage_bytes=0`.
- Last trend state: `MEMORY_STABLE`.
- Last watchdog snapshot was stale by `9181.4` seconds at checkpoint.

Failure condition:

- API and scheduler containers were both `exited/unhealthy`.
- Docker restart counts remained `0`.
- `OOMKilled=false` for both containers.
- `/health`, `/system-status`, and `/metrics` were unreachable on `localhost:8000`.

Final decision:

- Watchdog observability: `NO-GO`.
- Scheduler forensics: `PARTIAL`; restart provenance and drift are observable, but runtime continuity failed.
- Runtime protection: `NO-GO`.
- Trading/live changes: `NO-GO`.
