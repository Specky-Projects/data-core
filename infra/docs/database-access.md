# Acesso ao Banco

PostgreSQL nao deve ser exposto publicamente.

## SSH tunnel

Se o PostgreSQL estiver acessivel no host/container via localhost do servidor:

```bash
ssh -L 5433:localhost:5432 deploy@IP_DO_SERVIDOR
```

Se estiver apenas na rede Docker/Coolify, use um comando de port-forward temporario ou entre no container do Postgres via SSH.

## DBeaver/TablePlus

```text
Host: localhost
Port: 5433
Database: nome_do_banco
User: usuario_do_projeto
Password: senha_do_projeto
```

## URLs internas

Apps dentro da rede Docker/Coolify usam hostname interno:

```text
postgresql://poupi_baby_user:SENHA@postgres:5432/poupi_baby_db
```

Nunca use usuario admin do PostgreSQL nos apps.
