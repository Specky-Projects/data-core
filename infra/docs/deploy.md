# Deploy

## Projeto novo

1. Criar database e usuario no PostgreSQL compartilhado.
2. Criar `.env` do projeto no Coolify.
3. Configurar app/service no Coolify.
4. Definir health check.
5. Definir dominio se precisar HTTP publico.
6. Fazer primeiro deploy manual.
7. Confirmar logs e health.
8. Ativar deploy automatico via GitHub.

## Health checks

APIs devem expor `/health`.

Workers devem ter restart policy e logs claros. Se possivel, adicione comando de health interno ou metricas.

## Rollback

No Coolify:

- use deploy anterior quando disponivel;
- se migration alterou schema, tenha backup antes;
- evite migrations destrutivas sem janela de manutencao.
