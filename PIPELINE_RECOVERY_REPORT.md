# PIPELINE RECOVERY REPORT

Timestamp: 2026-05-25 America/Sao_Paulo.

## Scope

Final operational recovery of data-core runtime and crypto pipeline.

## Before

- Runtime was recovered but still DEGRADED.
- Crypto backlog after prior phase: 471.
- Crypto raw freshness was stale.
- `/ready` correctly returned 503.
- Pague Menos was healthy; Drogasil/Droga Raia were blocked.

## Actions

1. Captured runtime state, endpoints, metrics, DB counts, heartbeat and watchdog.
2. Ran controlled crypto normalization/analytics batches.
3. Classified ignored crypto raws by identity match.
4. Triggered one safe operational crypto collection via scheduler:

```powershell
docker compose exec -T scheduler python -c "from scheduler.jobs import collect_raw_job; collect_raw_job('crypto.crypto_coin_ohlcv')"
```

5. Processed the resulting raw delta with worker jobs.
6. Investigated Docker disk usage without pruning.
7. Isolated and fixed the pytest hang.

## Backlog recovery

Initial remaining backlog in this phase:

- `normalization_pending=371` at first snapshot in this phase.

Final:

- `normalization_pending=0`.
- `normalization_failed=0`.
- `ignored=557`.
- `normalized=57051`.

Classification:

- 557 ignored crypto raws match existing normalized market candles by identity.
- Remaining ignored rows are idempotent duplicates, not unprocessed backlog.

## Fresh collection proof

Final fresh run:

- Collector: `crypto.crypto_coin_ohlcv`.
- Started: 2026-05-25T10:56:08Z.
- Finished: 2026-05-25T10:56:43Z.
- Status: success.
- `raw_saved_count=10`.
- `error_count=0`.

The 10 raws were processed by normalization and classified as skipped/deduplicated.

## Metrics

Final observed:

- `raws_pending_total{module="crypto"} 0`.
- `normalization_failed_total{module="crypto"} 0`.
- `normalization_processed_total{module="crypto"}` increased during recovery.
- `analytics_processed_total{module="trading"}` increased during recovery.

## Test recovery

Problem:

- `pytest tests\test_scheduler_watchdog.py -q` hung.

Root cause:

- `test_scheduler_metrics_exposition` called global Prometheus `generate_latest()`.
- After DB-backed gauges were added, global registry exposition can invoke external DB callbacks in local test runs.

Fix:

- The test now validates watchdog metric gauge values directly.

Result:

- `18 passed in 0.76s`.

## Final state

DEGRADED.

Crypto is recovered, but production readiness remains NO-GO because provider coverage is degraded and disk pressure remains unresolved.
