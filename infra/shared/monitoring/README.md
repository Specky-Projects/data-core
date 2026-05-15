# Monitoring

Base inicial:

- Coolify logs por app;
- health checks por container;
- `docker compose ps` para servicos compartilhados;
- alertas futuros via Prometheus/Grafana/Alertmanager ou servico externo.

Este diretorio inclui um compose inicial de Prometheus/Grafana conectado na rede `infra_internal`.

Targets internos iniciais:

- `data-core-api:8000`;
- `poupi-baby-api:3000`.

Prioridade inicial:

1. Health checks HTTP para APIs.
2. Restart policy `unless-stopped`.
3. Logs por projeto no Coolify.
4. Backups testados.

Evolucao:

- Prometheus node exporter;
- cadvisor;
- Grafana;
- Alertmanager;
- alertas de disco, memoria, container unhealthy, erro de backup e filas paradas.
