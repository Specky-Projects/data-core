# Arquitetura Multi-Projetos

## Modelo

Um servidor Hetzner com Docker e Coolify gerencia varios projetos independentes.

Cada projeto tem:

- deploy separado;
- variaveis separadas;
- containers separados;
- logs separados no Coolify;
- dominio/subdominio proprio quando precisar HTTP publico;
- banco proprio dentro do PostgreSQL compartilhado.

## Banco

Escolha inicial: PostgreSQL compartilhado.

```text
postgres
  poupi_baby_db      owner poupi_baby_user
  data_core_db       owner data_core_user
  trading_bot_db     owner trading_bot_user
  analytics_db       owner analytics_user
```

O `trading_bot_db` fica reservado para estado operacional do bot. O runner legado do dominio `crypto_coin` ainda usa SQLite em volume Docker ate existir adapter PostgreSQL no storage do bot.

Quando migrar para PostgreSQL por projeto:

- carga alta ou imprevisivel;
- exigencia forte de isolamento;
- backup/restauracao independente frequente;
- extensoes conflitantes;
- projeto com SLA proprio.

## Redes

- rede interna para apps, PostgreSQL e Redis;
- reverse proxy/Coolify exposto em 80/443;
- banco e Redis sem porta publica.
