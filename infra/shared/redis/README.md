# Shared Redis

Redis comeca compartilhado para economizar recursos.

Convencao sugerida:

- DB 0: Coolify/infra, se necessario;
- DB 1: Poupi Baby queues/cache;
- DB 2: Data Core cache/rate limit;
- DB 3: trading bot;
- DB 4: telegram bots;
- DB 5+: automacoes futuras.

Em producao, Redis nao deve publicar porta no host. Use apenas rede interna Docker/Coolify.

Projetos com alta criticidade ou consumo imprevisivel devem migrar para Redis proprio.
