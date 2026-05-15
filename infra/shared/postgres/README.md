# Shared PostgreSQL

PostgreSQL de producao nao deve publicar porta no host. Apps acessam o banco pela rede interna Docker/Coolify.

Padrao:

- um database por projeto;
- um usuario por projeto;
- senha propria por projeto;
- backup por database;
- acesso humano apenas por SSH tunnel.

Exemplo de URL interna para app no mesmo ambiente Docker/Coolify:

```text
postgresql://data_core_user:SENHA@postgres:5432/data_core_db
```

Se o PostgreSQL for criado como recurso gerenciado no Coolify, use o hostname interno gerado pelo Coolify no lugar de `postgres`.
