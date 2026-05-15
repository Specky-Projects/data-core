# Operacao

## Rotina diaria

- conferir Coolify deployments;
- conferir containers unhealthy;
- conferir ultimo backup;
- conferir disco:

```bash
df -h
docker system df
```

## Rotina semanal

- aplicar updates de seguranca;
- testar restore de um backup recente em banco temporario;
- revisar logs de workers/scrapers;
- revisar dominios e SSL.

## Comandos uteis

```bash
docker ps
docker compose ps
docker logs --tail=200 CONTAINER
docker stats
ufw status verbose
```
