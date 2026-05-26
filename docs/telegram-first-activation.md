# Telegram-First Activation

Data: 2026-05-26

Objetivo: ativar alertas Telegram via Poupi System Bot sem remover o receiver webhook atual e sem commitar segredos.

## Estado Atual

- Poupi System Bot validado diretamente via `scripts/smoke-poupi-system-bot.ps1`.
- Alertmanager -> Poupi System Bot validado via `scripts/smoke-alertmanager-telegram.ps1`.
- Alertas `[SHADOW]` criados em `prometheus/rules/poupi_telegram_shadow_alerts.yml`.
- `promtool` validou 12 rules.
- `alertmanager/alertmanager.yml` original permanece intacto.

## Arquivos

- `alertmanager/alertmanager.telegram-first.yml`: template sem segredos.
- `alertmanager/poupi_telegram.tmpl`: template compacto de mensagem Telegram.
- `docker-compose.telegram-first.yml`: override para montar config renderizada e template.
- `scripts/render-alertmanager-telegram-first.ps1`: renderiza config final em `runtime-data`.
- `scripts/send-poupi-executive-summary.ps1`: envia summary executivo pelo Poupi System Bot.

## Ativacao Shadow

1. Renderizar config do Alertmanager:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\render-alertmanager-telegram-first.ps1
```

2. Subir monitoring com override Telegram-first:

```powershell
docker-compose -f docker-compose.yml -f docker-compose.telegram-first.yml --profile monitoring up -d alertmanager prometheus
```

3. Conferir readiness:

```powershell
curl http://127.0.0.1:9093/-/ready
curl http://127.0.0.1:9090/-/ready
```

4. Verificar regras carregadas:

```powershell
curl http://127.0.0.1:9090/api/v1/rules
```

5. Manter por 7 dias em shadow mode.

## Envio Manual Do Summary

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\send-poupi-executive-summary.ps1
```

Dry-run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\send-poupi-executive-summary.ps1 -DryRun
```

## Criterios De Promocao

Promover um alerta de `[SHADOW]` para producao somente quando:

- Dispara por causa real.
- Tem baixa duplicidade.
- Nao gera spam.
- Tem acao clara.
- Tem recovery funcionando.
- Aponta para dashboard correto.

## Rollback

Voltar ao Alertmanager original:

```powershell
docker-compose --profile monitoring up -d alertmanager
```

Ou subir sem o override:

```powershell
docker-compose -f docker-compose.yml --profile monitoring up -d alertmanager prometheus
```
