# Plano de Evolucao

Fase 1:

- um servidor Hetzner;
- Coolify;
- PostgreSQL compartilhado;
- Redis compartilhado;
- backups diarios;
- deploy por GitHub.

Fase 2:

- monitoramento Prometheus/Grafana;
- alertas de backup, disco e container unhealthy;
- usuario read-only para dashboards;
- Cloudflare ou equivalente para DNS/WAF basico.

Fase 3:

- separar PostgreSQL por projeto critico;
- storage externo para backups;
- replica/read-only se houver necessidade;
- runners dedicados para scrapers pesados.

Evitar por enquanto:

- Kubernetes;
- service mesh;
- multiplos servidores sem necessidade;
- microservicos artificiais.
