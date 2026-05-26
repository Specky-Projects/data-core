# Runtime Memory Pressure Report

Generated at: `2026-05-25T21:18:58.891043+00:00`

## Executive Summary

- Watchdog samples: `1813` over `32.0381` hours.
- Reliability audit decisions: `55` over `18.8673` hours.
- Scheduler drift events: `5`.
- Lifecycle events: `18`.
- Latest restart source: `probe_only`.
- Real restart count: `0`.
- False/legacy restart count candidate: `0`.
- Probe boot count: `10`.

## Memory And Swap

- Current RSS/cgroup memory: `225144832` bytes.
- Max observed cgroup memory: `791666688` bytes.
- Current memory limit: `None`.
- Current swap usage: `0` bytes.
- Max observed swap usage: `29589504` bytes.
- Max memory growth rate: `682472.1402773953` bytes/second.
- Memory events: `{"high": 0, "low": 0, "max": 0, "oom": 0, "oom_group_kill": 0, "oom_kill": 0}`.

## Scheduler Reliability Correlation

- Modes: `{'NORMAL': 10, 'CRITICAL_PROTECTION': 45}`.
- Diagnosis states: `{'SCHEDULER_HEALTHY': 10, 'SCHEDULER_RESTART_LOOP': 45}`.
- Priorities: `{'LOW': 12, 'NORMAL': 12, 'HIGH': 31}`.
- Post-deploy reliability decisions: `0`.
- Max APScheduler drift: `54.772003` seconds.

## Root-Cause Finding

The observed critical dominance is attributable to an untrusted restart counter in the scheduler snapshot when `restart_count_source` is absent. The snapshot shows no cgroup OOM events and no memory-limit ratio, while memory is stable. The hardened watchdog now treats that evidence as false/legacy provenance unless an explicit container/runtime source reports real restarts.

## Capacity Remediation Plan

- Keep `SCHEDULER_RELIABILITY_ENABLED=false` and `SCHEDULER_RELIABILITY_DRY_RUN=true`.
- Scheduler runtime has been refreshed with the hardened probe.
- Continue passive dry-run observation until 6h or 24 post-deploy decisions are available.
- Watch `watchdog_confidence_score`, `scheduler_false_restart_total`, `scheduler_restart_real_total`, `scheduler_execution_drift_seconds`, and `runtime_memory_pressure_score`.
- Do not enable runtime protection while restart provenance is `legacy_or_probe_local` or confidence is below `0.8`.

## Passive Window Final Checkpoint - 2026-05-26T17:02Z

- Elapsed time since controlled API/scheduler deploy: `30.3722` hours.
- Post-deploy dry-run decisions: `3`.
- Post-deploy decision modes: `NORMAL=3`.
- Drift events: `68`.
- Average APScheduler drift: `8.634050411764704` seconds.
- Max APScheduler drift: `54.772003` seconds.
- Latest restart source: `probe_only`.
- Observed restart count: `0`.
- OOM kill count: `0`.
- Swap usage: `0` bytes.
- Memory trend: `MEMORY_STABLE`.
- Last watchdog snapshot age at checkpoint: `9181.4` seconds.
- API container: `exited/unhealthy`, `restartCount=0`, `OOMKilled=false`.
- Scheduler container: `exited/unhealthy`, `restartCount=0`, `OOMKilled=false`.
- `/health`, `/system-status`, and `/metrics` were unreachable.

Decision:

- Memory pressure did not explain a real restart loop in the final checkpoint.
- Restart provenance stayed non-real (`probe_only`) with no Docker restart or OOM evidence.
- Runtime continuity failed, so runtime protection remains `NO-GO`.
