# Visão Geral — CryptoBot

Bot de trading automático de criptomoedas baseado em análise técnica multi-indicador.

## O que faz

Opera um único par (ex.: BTC/USDT) em uma exchange (Binance, Bybit ou KuCoin) comprando e vendendo automaticamente com base em:

- Cruzamento de médias móveis (MA fast / MA slow)
- RSI (sobrevendido/sobrecomprado)
- Bandas de Bollinger (suporte/resistência)
- ADX (força da tendência — distingue mercado direcional de lateral)
- Volume (confirma movimentos)

Cada sinal recebe um **score de confiança 0–100**. Só entra em posição acima de 55.

## Modos

| Modo | Descrição |
|------|-----------|
| Paper trading | Simulação com saldo virtual (padrão) |
| Live trading | Ordens reais na exchange via API |

## Recursos principais

- **Trailing stop** — stop sobe automaticamente com o preço, travando lucro
- **Multi-timeframe** — confirma tendência no TF superior antes de comprar
- **Position sizing dinâmico** — investe % maior quando confiança é alta
- **Auto-tuner genético** — otimiza parâmetros semanalmente com dados reais
- **Backtesting** — testa estratégia em histórico antes de ir ao vivo
- **Alertas Telegram** — notificações de compra/venda em tempo real
- **Reconexão automática** — backoff exponencial em quedas de API

## Entry points

| Comando | Descrição |
|---------|-----------|
| `python bot.py` | Inicia o bot em loop |
| `python backtest.py` | Roda backtest no histórico |
| `python autotune.py` | Otimização genética manual |
| `python deploy.py <ip>` | Deploy para VPS Linux |
