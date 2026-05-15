# Stack

## Linguagem e runtime

- **Python 3.10+** — asyncio nativo, dataclasses, match/case
- **pip + pyproject.toml** — gerenciamento de dependências

## Dependências principais

| Pacote | Versão | Uso |
|--------|--------|-----|
| `ccxt` | ≥4.3.0 | Abstração de exchanges (Binance, Bybit, KuCoin) |
| `pandas` | ≥2.0 | Séries temporais de OHLCV, cálculo de indicadores |
| `numpy` | ≥1.26 | Operações vetoriais (RSI, BB, ADX) |
| `aiohttp` | ≥3.9 | HTTP async (Telegram notifier) |
| `python-dotenv` | ≥1.0 | Leitura do `.env` |

## Dependências de dev

| Pacote | Uso |
|--------|-----|
| `pytest` | Testes unitários |
| `pytest-asyncio` | Testes de código async |

## Infraestrutura

- **Deploy:** VPS Linux (Hetzner/DigitalOcean/Oracle) via script `deploy.py`
- **Processo:** systemd service (`cryptobot.service`)
- **Logs:** arquivos `.log` + `.jsonl` em `logs/`
- **Alertas:** Telegram Bot API

## Exchanges suportadas

| Exchange | Spot | Testnet |
|----------|------|---------|
| Binance | ✅ | — |
| Bybit | ✅ | — |
| KuCoin | ✅ (requer passphrase) | — |
