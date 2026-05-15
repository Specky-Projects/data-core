# Backup e Restore

## PostgreSQL

Backup diario por database:

```bash
cd /opt/infra
BACKUP_DIR=/opt/infra/backups/postgres ./shared/backups/backup-postgres.sh
```

Restore:

```bash
./shared/backups/restore-postgres.sh data_core_db /opt/infra/backups/postgres/data_core_db_YYYYMMDDTHHMMSSZ.dump.gz
```

## Volumes

Antes de upgrades grandes:

```bash
docker run --rm -v multi_project_infra_postgres-data:/data -v "$PWD/backups:/backup" alpine tar czf /backup/postgres-volume.tgz -C /data .
```

## Retencao

Minimo inicial:

- diarios por 14 dias;
- copia externa semanal;
- teste de restore mensal.

Backups nao testados sao apenas esperanca. Teste restauracao em banco temporario.
