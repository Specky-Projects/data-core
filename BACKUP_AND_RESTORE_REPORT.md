# Backup And Restore Report

Date: 2026-05-25 / 2026-05-26 UTC

## Backup Location

Backup root:

`/mnt/HC_Volume_105715453/poupi-backups/20260525T205906Z`

Size:

`79M`

Permissions:

Backup root was created with restricted permissions (`700`).

## Backed Up Items

### PostgreSQL Logical Dumps

Running Postgres containers were backed up with globals plus per-database custom-format dumps:

- `poupi-crypto-db-1`
  - `postgres`
  - `poupi_crypto`
- `multi_project_infra-postgres-1`
  - `analytics_db`
  - `data_core_db`
  - `postgres`
  - `poupi_baby_db`
  - `poupi_crypto_db`
  - `poupi_jobs_db`
  - `trading_bot_db`
- `coolify-db`
  - `coolify`
  - `postgres`

### Volume Archives

Volume archives were created for:

- `prometheus-data`
- `q11p1efg13of6ujrfgu25lal_grafana-data`
- `poupi_crypto_signal_dataset`
- `dvq6dwsagsw4p4oqwuw7bak9_runtime-data`
- `dvq6dwsagsw4p4oqwuw7bak9_runtime-logs`
- `poupi-baby_postgres-data`
- `poupi-jobs_pgdata`

### Config / Manifest Evidence

Saved:

- Docker ps/images/volumes/networks/system-df inventory
- Coolify application compose/config directory backup
- Firewall guard script and systemd unit
- SHA256 checksums

## Restore Test

Restore test was performed in a disposable PostgreSQL container using tmpfs storage.

The first restore attempt surfaced missing role grants in the isolated test container. This was expected because production roles were not recreated in the temporary restore environment. The restore test was rerun with:

- `--no-owner`
- `--no-acl`

Final result:

- Restore test: PASS.
- Dumps restored: 11.

Restored database table counts:

- `coolify`: 64 tables.
- `postgres`: 0 tables.
- `analytics_db`: 0 tables.
- `data_core_db`: 44 tables.
- `poupi_baby_db`: 24 tables.
- `poupi_crypto_db`: 3 tables.
- `poupi_jobs_db`: 0 tables.
- `trading_bot_db`: 0 tables.
- `poupi_crypto`: 13 tables.

Restore test log:

`/mnt/HC_Volume_105715453/poupi-backups/20260525T205906Z/restore-test/restore-test-retry.log`

## Important Notes

- Production volumes were not overwritten.
- Production databases were not restored into or reset.
- Temporary restore container was removed after the test.
- Backups contain sensitive operational data and must not be committed to Git.

## Remaining Work

- Schedule recurring backups.
- Add off-server replication or object storage.
- Add backup retention policy.
- Add automated checksum verification.
- Add periodic restore rehearsal.
- Decide whether stopped legacy DB volumes should receive deeper forensic backup before any cleanup.

## Decision

- Backup exists: YES.
- Restore proven: YES, for logical PostgreSQL dumps in isolated restore mode.
- Production overwrite risk: avoided.
- Database migration readiness: still NO-GO until recurring backup and rollback runbook are approved.
