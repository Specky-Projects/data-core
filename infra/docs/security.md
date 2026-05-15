# Segurança

## Principios

- banco e Redis sem porta publica;
- segredos somente no Coolify ou `.env` real no servidor;
- SSH com chave;
- firewall deny-by-default;
- menor numero possivel de dominios publicos;
- workers sem porta publica.

## Portas publicas

Permitidas:

- `22/tcp`;
- `80/tcp`;
- `443/tcp`.

Evite publicar:

- `5432`;
- `6379`;
- portas internas de workers;
- dashboards sem autenticacao.

## Segredos

Nao versionar:

- `.env`;
- dumps de banco;
- tokens Telegram;
- chaves de exchanges;
- API keys;
- credenciais SMTP.

## Acesso de banco

Use SSH tunnel. Crie usuarios separados por projeto. Revogue credenciais quando alguem sair do projeto.
