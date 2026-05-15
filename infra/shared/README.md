# Servicos Compartilhados

Servicos compartilhados reduzem custo e simplificam a primeira operacao.

Incluidos:

- PostgreSQL central com database e usuario por projeto;
- Redis compartilhado com senha e databases numerados por projeto;
- scripts de backup/restore;
- orientacao inicial de monitoramento.

Se um projeto crescer ou exigir isolamento mais forte, migre apenas esse projeto para Postgres/Redis dedicados.
