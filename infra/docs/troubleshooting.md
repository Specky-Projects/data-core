# Troubleshooting

## App nao sobe

1. Ver logs no Coolify.
2. Verificar variaveis obrigatorias.
3. Confirmar conexao interna com PostgreSQL/Redis.
4. Rodar migration manualmente se necessario.
5. Conferir health check.

## Banco inacessivel

- confirmar que app esta na mesma rede interna;
- confirmar hostname interno;
- confirmar usuario/database;
- confirmar que PostgreSQL esta healthy;
- nao abrir porta publica como atalho.

## SSL nao emite

- confirmar DNS apontando para o servidor;
- confirmar porta 80/443 abertas;
- confirmar dominio configurado no recurso certo;
- aguardar propagacao DNS.

## Disco cheio

```bash
docker system df
docker image prune
docker builder prune
```

Nao remova volumes sem backup.
