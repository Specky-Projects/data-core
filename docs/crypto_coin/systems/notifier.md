# Sistema: Notifier (Telegram)

**Arquivo:** `src/notifier.py` — classe `Notifier`

## Configuração

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=<token do @BotFather>
TELEGRAM_CHAT_ID=<seu chat_id>
```

Para desativar: `TELEGRAM_ENABLED=false` (padrão).

## Como obter o chat_id

1. Inicie conversa com seu bot no Telegram
2. Acesse `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Procure o campo `chat.id`

## Mensagens enviadas

| Evento | Quando |
|--------|--------|
| Bot iniciado | Na subida |
| COMPRA | Ao entrar em posição |
| VENDA | Ao sair de posição (com P&L) |
| Perda diária atingida | Quando `MAX_DAILY_LOSS_PCT` é ultrapassado |
| Bot encerrado | No shutdown |
| Relatório semanal | Toda segunda-feira |

## Comportamento de erro

Se o Telegram falhar (rede, token inválido), o erro é logado mas **não interrompe o bot**. O trading continua normalmente.
