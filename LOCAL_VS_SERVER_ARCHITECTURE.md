# Local vs Server Architecture

## Target split

| Component | Local notebook | Server |
| --- | --- | --- |
| Frontend development | Yes | Optional deploy target |
| Manual scripts | Yes | Optional |
| Tests and debugging | Yes | CI/validation |
| Replay/statistical analysis | Yes | Optional batch jobs |
| APIs | On demand only | Always on |
| Schedulers | No always-on | Always on |
| Workers | No always-on | Always on |
| Redis | On demand only | Persistent |
| Postgres | On demand only | Persistent |
| Prometheus | On demand only | Always on |
| Grafana | On demand only | Always on |
| Alertmanager | On demand only | Always on |

## Migration order

1. Move observability to the server.
2. Move schedulers and workers.
3. Move APIs.
4. Move Redis and Postgres persistent workloads.

## Migration requirements

Every server move needs:

- backup before migration
- rollback command and ownership
- healthcheck validation
- volume mapping
- secret inventory
- firewall review
- DNS and TLS review
- post-deploy monitoring

## Duplicate runtime risk

Schedulers and workers must not run both locally and on the server unless an
explicit isolation plan exists. The local notebook should default to stopped
runtime containers.

## Local disk policy

The notebook is currently disk-constrained. Avoid local always-on Docker usage,
frequent image rebuilds, and long-lived local monitoring retention. Use:

```powershell
docker builder prune
```

only when approved and never with volume pruning.

