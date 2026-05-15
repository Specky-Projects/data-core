# Dashboards

Dashboards internos devem ficar atras de autenticacao e dominio proprio.

Exemplos:

- `dash.example.com`;
- `grafana.example.com`;
- `ops.example.com`.

Evite conectar dashboards direto no PostgreSQL com usuario admin. Use usuario read-only quando possivel.
