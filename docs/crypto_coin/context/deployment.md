# Deploy

## Requisitos do servidor

- Ubuntu 20.04+ (ou Debian)
- Python 3.10+
- 1 GB RAM mínimo

## Deploy automatizado

```bash
python deploy.py <IP> --user root --key ~/.ssh/id_rsa
```

O script `deploy.py`:
1. Conecta via SSH
2. Instala dependências (`install.sh`)
3. Faz upload dos arquivos
4. Configura systemd service
5. Inicia o bot

## Gerenciar o serviço no servidor

```bash
# Status
systemctl status cryptobot

# Logs em tempo real
journalctl -u cryptobot -f

# Reiniciar
systemctl restart cryptobot

# Parar
systemctl stop cryptobot
```

## Variáveis de ambiente no servidor

O `.env` fica em `/home/cryptobot/bot/.env`. Para editar:

```bash
ssh root@<IP>
cd /home/cryptobot/bot
nano .env
systemctl restart cryptobot
```

## Atualizar o bot

```bash
python deploy.py <IP> --user root --key ~/.ssh/id_rsa --update-only
```

## Logs no servidor

```
/home/cryptobot/bot/logs/bot.log         ← log principal
/home/cryptobot/bot/logs/trades_*.jsonl  ← histórico de trades por par
/home/cryptobot/bot/logs/bot_metrics.jsonl
```
