"""
TradingBot v4 — loop principal com todas as melhorias integradas

  1. Trailing Stop Loss        — stop sobe com o preço, trava lucro
  2. Reconexão automática      — backoff exponencial em quedas de conexão
  3. Multi-timeframe           — confirma tendência no TF superior antes de entrar
  4. Position sizing dinâmico  — investe mais quando confiança é alta
  5. Relatório semanal         — resumo automático toda segunda-feira
"""

import asyncio
import json
import traceback
import uuid
from dataclasses import asdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from domains.crypto_coin.config.settings import Config
from domains.crypto_coin.core.execution.exchange_connector import ExchangeConnector
from domains.crypto_coin.data.storage import (
    BotError,
    BotRun,
    EntryContext,
    EquityPoint,
    MarketSnapshot,
    OpenPositionState,
    RegimeRecord,
    ShadowTrade,
    SignalDecision,
    TradeResult,
    create_storage,
)
from domains.crypto_coin.analytics.decision_support import regime_entry_decision
from domains.crypto_coin.analytics.loss_classification import classify_loss
from domains.crypto_coin.analytics.overtrading import overtrading_decision
from domains.crypto_coin.analytics.setup_quality import compute_setup_score
from domains.crypto_coin.indicators.technical import compute_indicators
from domains.crypto_coin.strategies.trend_following.strategy import MIN_CONFIDENCE, Signal, get_signal, signal_description
from domains.crypto_coin.infra.notifier import Notifier
from domains.crypto_coin.core.risk.trailing_stop import TrailingStop
from domains.crypto_coin.core.engine.reconnect import ReconnectionManager
from domains.crypto_coin.indicators.mtf import MultiTimeframeAnalyzer, MTFBias
from domains.crypto_coin.core.risk.position_sizing import PositionSizer
from domains.crypto_coin.analytics.reports.weekly import send_weekly_report
from domains.crypto_coin.analytics.metrics.append import append_metric
from domains.crypto_coin.autotune.scheduler import WeeklyScheduler

TIMEFRAME_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900,
    "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400,
}


class TradingBot:
    def __init__(self, cfg: Config, logger, shutdown_event: Optional[asyncio.Event] = None):
        self.cfg       = cfg
        self.logger    = logger
        self.connector = ExchangeConnector(cfg, logger)
        self.notifier  = Notifier(cfg, logger)
        self.storage   = create_storage(cfg.storage_url)
        self._shutdown = shutdown_event
        self.run_id    = str(uuid.uuid4())
        self._restored_position_state = False

        # Estado
        self.in_position:      bool  = False
        self.buy_price:        Optional[float] = None
        self.position_size:    float = 0.0
        self.entry_confidence: int   = 0
        self.trailing_stop:    Optional[TrailingStop] = None
        self.position_low:     Optional[float] = None
        self.position_high:    Optional[float] = None

        # Métricas
        self.trades_today:      int   = 0
        self.pnl_today:         float = 0.0
        self.total_trades:      int   = 0
        self.winning_trades:    int   = 0
        self.total_pnl:         float = 0.0
        self.day_start_balance: float = 0.0
        self.current_day:       date  = date.today()
        self._last_report:      Optional[date] = None

        # Módulos
        self.reconnect = ReconnectionManager(logger)
        self.mtf       = MultiTimeframeAnalyzer(cfg, self.connector, logger)
        self.sizer     = PositionSizer(base_pct=cfg.trade_size_pct)
        self.scheduler = WeeklyScheduler(
            cfg=cfg, logger=logger,
            interval_days=cfg.autotune_interval_days,
            run_hour=cfg.autotune_hour,
            train_days=60, val_days=14,
            population=40, generations=25,
            min_val_return=0.0, restart_bot_after=True,
        )
        self.running = False

    # ── Ciclo principal ───────────────────────────────────────

    async def run(self):
        self.storage.init_schema()
        self.storage.start_bot_run(
            BotRun(
                run_id=self.run_id,
                started_at=datetime.utcnow(),
                symbol=self.cfg.symbol,
                timeframe=self.cfg.timeframe,
                paper=self.cfg.paper_trading,
                metadata={"strategy_version": self.cfg.strategy_version},
            )
        )
        await self.connector.connect()
        self._restore_open_position_state()
        await self.notifier.send(
            f"🤖 Bot v4 iniciado\n"
            f"Par: {self.cfg.symbol} | {self.cfg.timeframe}\n"
            f"Trailing stop ✅ | MTF ✅ | Sizing dinâmico ✅"
        )
        bal = await self.connector.get_balances()
        self._reconcile_restored_position(bal)
        self.day_start_balance = self._quote_free(bal) or self.cfg.paper_initial_balance

        self.running   = True
        sleep_secs     = TIMEFRAME_SECONDS.get(self.cfg.timeframe, 900)
        self.logger.info(f"⏱  Loop a cada {sleep_secs}s | Par: {self.cfg.symbol}")

        try:
            while self.running:
                if self._shutdown and self._shutdown.is_set():
                    self.running = False
                    break
                try:
                    await self.scheduler.maybe_run(bot=self)
                    await self._maybe_send_weekly_report()
                    await self._tick()
                except Exception as e:
                    self._save_bot_error("tick", e)
                    self.logger.error(f"Erro no tick: {e}", exc_info=True)
                    await asyncio.sleep(30)

                append_metric(
                    self.logger,
                    {
                        "event": "tick_cycle",
                        "symbol": self.cfg.symbol,
                        "timeframe": self.cfg.timeframe,
                        "running": self.running,
                    },
                )

                self.logger.info(f"💤 Aguardando {sleep_secs}s até próxima vela...")
                if self._shutdown:
                    try:
                        await asyncio.wait_for(self._shutdown.wait(), timeout=sleep_secs)
                        self.running = False
                        break
                    except asyncio.TimeoutError:
                        pass
                else:
                    await asyncio.sleep(sleep_secs)
        except asyncio.CancelledError:
            self.running = False
            self.storage.finish_bot_run(self.run_id, "cancelled")
            raise

    # ── Tick ─────────────────────────────────────────────────

    async def _tick(self):
        self._check_day_reset()

        # 1. Candles com retry automático
        df = await self.reconnect.execute(
            self.connector.fetch_ohlcv, limit=150, label="fetch_ohlcv"
        )
        if df is None:
            self.logger.warning("Sem dados de mercado — pulando tick.")
            return

        # 2. Indicadores
        ind = compute_indicators(df, self.cfg)
        if ind is None:
            self.logger.warning("Indicadores insuficientes — aguardando mais candles.")
            return

        price = ind.close
        self._log_indicators(price, ind)
        candle_time = self._last_candle_time(df)
        self._save_market_state(df, ind, candle_time)
        self._update_shadow_trades(df, candle_time)

        # 3. Trailing stop (verifica antes de qualquer outra coisa)
        if self.in_position and self.trailing_stop:
            self._update_position_extremes(price)
            if self.trailing_stop.update(price):
                self.logger.info(f"🔔 Trailing stop acionado! {self.trailing_stop.summary()}")
                await self._execute_sell(price, Signal.STOP_LOSS, reason="trailing stop")
                return
            self.logger.info(f"📍 {self.trailing_stop.summary()}")

        # 4. Limite de perda diária
        if self._daily_loss_breached():
            self.logger.warning("🚨 Limite de perda diária atingido!")
            await self.notifier.send("🚨 PERDA DIÁRIA MÁXIMA ATINGIDA — bot pausado até meia-noite.")
            await asyncio.sleep(self._seconds_until_midnight())
            return

        # 5. Retorno acumulado vs B&H
        bal = await self.connector.get_balances()
        quote_free = self._quote_free(bal)
        current_total = quote_free + (self.position_size * price if self.in_position else 0)
        strategy_return_pct = (
            (current_total - self.cfg.paper_initial_balance)
            / self.cfg.paper_initial_balance * 100
        )
        adx_s = f"{ind.adx:.1f}" if ind.adx is not None else "N/A"
        vol_s = f"{ind.volume_ratio:.2f}" if ind.volume_ratio is not None else "N/A"
        self.logger.info(
            f"🧠 Regime: {ind.regime.value} | Confiança: {ind.confidence}/100 | "
            f"ADX: {adx_s} | "
            f"Vol: {vol_s}x | "
            f"B&H: {ind.buy_and_hold_pct:+.1f}% | Bot: {strategy_return_pct:+.1f}%"
        )

        # 6. Multi-timeframe (só para entradas novas)
        mtf_bias = MTFBias.NEUTRAL
        if not self.in_position:
            mtf_bias = await self.mtf.get_bias()

        # 7. Sinal
        signal = get_signal(ind, self.in_position, self.buy_price, self.cfg, strategy_return_pct)
        self.logger.info(f"📊 {signal_description(signal, ind)}")
        self._save_equity_point(candle_time, price, quote_free, current_total)
        setup = compute_setup_score(ind, mtf_bias.value)

        # 8. Filtro MTF — bloqueia compra se TF superior estiver em baixa
        if signal in (Signal.BUY, Signal.RANGE_BUY):
            if not self.mtf.allows_buy(mtf_bias):
                self._save_signal_decision(
                    candle_time,
                    signal,
                    price,
                    ind,
                    accepted=False,
                    reason="blocked_mtf",
                    mtf_bias=mtf_bias.value,
                    strategy_return_pct=strategy_return_pct,
                    setup=setup,
                )
                self.logger.info(f"🚫 Compra bloqueada pelo MTF — viés: {mtf_bias.value}")
                return
            decision = regime_entry_decision(
                self.storage,
                symbol=self.cfg.symbol,
                timeframe=self.cfg.timeframe,
                regime=ind.regime.value,
            )
            if not decision.allow_entry:
                self._save_signal_decision(
                    candle_time,
                    signal,
                    price,
                    ind,
                    accepted=False,
                    reason="blocked_weak_regime",
                    mtf_bias=mtf_bias.value,
                    strategy_return_pct=strategy_return_pct,
                    setup=setup,
                )
                self.logger.info(f"Compra bloqueada pelo storage: {decision.reason}")
                return
            if decision.confidence_adjustment and ind.confidence < MIN_CONFIDENCE + decision.confidence_adjustment:
                self._save_signal_decision(
                    candle_time,
                    signal,
                    price,
                    ind,
                    accepted=False,
                    reason="blocked_adaptive_confidence",
                    mtf_bias=mtf_bias.value,
                    strategy_return_pct=strategy_return_pct,
                    setup=setup,
                )
                self.logger.info(
                    f"Compra bloqueada por confianca adaptativa: "
                    f"{ind.confidence}/100 | ajuste +{decision.confidence_adjustment} | {decision.reason}"
                )
                return
            guard = overtrading_decision(
                self.storage,
                symbol=self.cfg.symbol,
                strategy_id="trend_following",
                now=candle_time,
                max_trades_per_day=self.cfg.max_trades_per_day,
                cooldown_after_loss_minutes=self.cfg.cooldown_after_loss_minutes,
                max_consecutive_losses=self.cfg.max_consecutive_losses,
            )
            if not guard.allow_entry:
                self._save_signal_decision(
                    candle_time,
                    signal,
                    price,
                    ind,
                    accepted=False,
                    reason=f"blocked_overtrading_{guard.reason}",
                    mtf_bias=mtf_bias.value,
                    strategy_return_pct=strategy_return_pct,
                    setup=setup,
                )
                self.logger.info(f"Compra bloqueada por protecao contra overtrading: {guard.reason}")
                return
            self._save_signal_decision(
                candle_time,
                signal,
                price,
                ind,
                accepted=True,
                reason="accepted_entry",
                mtf_bias=mtf_bias.value,
                strategy_return_pct=strategy_return_pct,
                setup=setup,
            )
            self._save_entry_context(
                candle_time,
                signal,
                price,
                ind,
                mtf_bias.value,
                strategy_return_pct,
                setup,
            )
            self._open_shadow_trade(candle_time, signal, price, ind, mtf_bias.value, setup)
        elif signal == Signal.HOLD:
            self._save_signal_decision(
                candle_time,
                signal,
                price,
                ind,
                accepted=False,
                reason="hold",
                mtf_bias=mtf_bias.value,
                strategy_return_pct=strategy_return_pct,
                setup=setup,
            )
        elif signal == Signal.PAUSED_BNH:
            self._save_signal_decision(
                candle_time,
                signal,
                price,
                ind,
                accepted=False,
                reason="blocked_buy_and_hold",
                mtf_bias=mtf_bias.value,
                strategy_return_pct=strategy_return_pct,
                setup=setup,
            )

        # 9. Executa
        if signal in (Signal.BUY, Signal.RANGE_BUY):
            await self._execute_buy(price, ind.confidence)
        elif signal in (Signal.SELL, Signal.STOP_LOSS, Signal.TAKE_PROFIT, Signal.RANGE_SELL):
            self._save_signal_decision(
                candle_time,
                signal,
                price,
                ind,
                accepted=True,
                reason="accepted_exit",
                mtf_bias=mtf_bias.value,
                strategy_return_pct=strategy_return_pct,
                setup=setup,
            )
            await self._execute_sell(price, signal)

    # ── Ordens ───────────────────────────────────────────────

    async def _execute_buy(self, price: float, confidence: int = 60):
        bal = await self.connector.get_balances()
        quote = self._quote_free(bal)
        spend = self.sizer.usdt_amount(quote, confidence)
        qc = self.cfg.quote_currency

        if spend < 10:
            self.logger.warning(f"Ordem muito pequena ou saldo insuficiente ({spend:.2f} {qc}).")
            return

        self.logger.info(f"💡 {self.sizer.explain(confidence)} → {spend:.2f} {qc}")

        result = await self.reconnect.execute(
            self.connector.buy, spend, label="ordem de compra"
        )
        if not result:
            return

        self.in_position      = True
        self.buy_price        = result["price"]
        self.position_size    = result["amount"]
        self.entry_confidence = confidence
        self.total_trades    += 1

        self.trailing_stop = TrailingStop(
            buy_price=price,
            trail_pct=self.cfg.stop_loss_pct,
            activate_pct=1.0,
        )
        self.position_low = result["price"]
        self.position_high = result["price"]

        msg = (
            f"🟢 COMPRA — {self.cfg.symbol}\n"
            f"   Preço:      ${price:,.2f}\n"
            f"   Qtd:        {result['amount']:.6f}\n"
            f"   Valor:      {result['cost']:.2f} {qc}\n"
            f"   Confiança:  {confidence}/100\n"
            f"   Stop trail: ${price*(1-self.cfg.stop_loss_pct/100):,.2f}\n"
            f"   Take profit:${price*(1+self.cfg.take_profit_pct/100):,.2f}"
        )
        self.logger.info(msg)
        await self.notifier.send(msg)
        self._save_trade("BUY", result, confidence=confidence)
        self._save_trade_result(
            "BUY",
            result,
            requested_price=price,
            confidence=confidence,
        )
        self._save_open_position_state(quote_balance=max(0.0, quote - result.get("cost", spend)))

    async def _execute_sell(self, price: float, signal: Signal, reason: str = ""):
        if not self.in_position or self.position_size <= 0:
            return

        result = await self.reconnect.execute(
            self.connector.sell, self.position_size, label="ordem de venda"
        )
        if not result:
            return

        pnl     = (price - self.buy_price) * self.position_size
        pnl_pct = ((price - self.buy_price) / self.buy_price) * 100
        self._update_position_extremes(price)
        mae, mfe = self._mae_mfe()
        self.pnl_today += pnl
        self.total_pnl += pnl
        if pnl > 0:
            self.winning_trades += 1

        emoji      = "💰" if signal == Signal.TAKE_PROFIT else ("🔴" if pnl < 0 else "🟡")
        reason_str = f" ({reason})" if reason else ""
        peak_str   = f"\n   Pico atingido: ${self.trailing_stop.highest_price:,.2f}" if self.trailing_stop else ""
        qc = self.cfg.quote_currency

        msg = (
            f"{emoji} VENDA{reason_str} [{signal.value}]\n"
            f"   Par:     {self.cfg.symbol}\n"
            f"   Entrada: ${self.buy_price:,.2f} | Saída: ${price:,.2f}\n"
            f"   P&L:     {pnl:+.2f} {qc} ({pnl_pct:+.2f}%){peak_str}\n"
            f"   Win rate: {self._win_rate()}% | P&L total: {self.total_pnl:+.2f} {qc}"
        )
        self.logger.info(msg)
        await self.notifier.send(msg)
        self._save_trade("SELL", result, pnl=pnl, signal=signal.value)
        self._save_trade_result(
            "SELL",
            result,
            requested_price=price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            signal=signal.value,
            mae=mae,
            mfe=mfe,
        )

        self.in_position      = False
        self.buy_price        = None
        self.position_size    = 0.0
        self.entry_confidence = 0
        self.trailing_stop    = None
        self.position_low     = None
        self.position_high    = None
        self.storage.clear_open_position_state(self.cfg.symbol, "trend_following")

    # ── Relatório semanal ─────────────────────────────────────

    async def _maybe_send_weekly_report(self):
        today = date.today()
        if today.weekday() == 0 and today != self._last_report:
            self._last_report = today
            bal = await self.connector.get_balances()
            quote = self._quote_free(bal)
            if self.in_position and self.position_size > 0:
                mark = await self.connector.get_ticker_price()
                if mark is None:
                    mark = self.buy_price or 0
                total = quote + self.position_size * mark
            else:
                total = quote
            ret = ((total - self.cfg.paper_initial_balance) / self.cfg.paper_initial_balance) * 100
            report = await send_weekly_report(self.cfg, self.notifier, ret)
            self.logger.info(f"📋 Relatório semanal:\n{report}")

    # ── Utilitários ───────────────────────────────────────────

    @staticmethod
    def _quote_free(bal: dict) -> float:
        if not bal:
            return 0.0
        q = bal.get("quote")
        return float(q) if q is not None else 0.0

    def _log_indicators(self, price: float, ind):
        rsi_s = f"{ind.rsi:.1f}"     if ind.rsi     is not None else "N/A"
        maf_s = f"{ind.ma_fast:.2f}" if ind.ma_fast is not None else "N/A"
        mas_s = f"{ind.ma_slow:.2f}" if ind.ma_slow is not None else "N/A"
        atr_s = f"{ind.atr:.2f}"     if ind.atr     is not None else "N/A"
        bk_s  = f"{ind.breakout_score:.0f}" if hasattr(ind, "breakout_score") else "N/A"
        hv_s  = f"{ind.hv:.0f}%"     if getattr(ind, "hv", None) is not None else "N/A"
        self.logger.info(
            f"📈 {self.cfg.symbol} ${price:,.2f} | "
            f"RSI={rsi_s} | "
            f"MAf={maf_s} | "
            f"MAs={mas_s} | "
            f"ATR={atr_s} | "
            f"BK={bk_s} | "
            f"HV={hv_s} | "
            f"Posição={'SIM' if self.in_position else 'NÃO'}"
        )

    def _daily_loss_breached(self) -> bool:
        if not self.day_start_balance:
            return False
        return (self.pnl_today / self.day_start_balance * 100) <= -self.cfg.max_daily_loss_pct

    def _check_day_reset(self):
        today = date.today()
        if today != self.current_day:
            self.logger.info("🌅 Novo dia — resetando contadores diários.")
            self.trades_today = 0
            self.pnl_today    = 0.0
            self.current_day  = today

    def _win_rate(self) -> int:
        if self.total_trades == 0:
            return 0
        return int((self.winning_trades / self.total_trades) * 100)

    def _seconds_until_midnight(self) -> int:
        midnight = datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
        return int((midnight - datetime.now()).total_seconds())

    def _save_trade(self, side: str, result: dict, pnl: float = None,
                    signal: str = None, confidence: int = None):
        Path("logs").mkdir(exist_ok=True)
        safe_symbol = self.cfg.symbol.replace("/", "_")
        record = {
            "timestamp":  datetime.utcnow().isoformat(),
            "symbol":     self.cfg.symbol,
            "side":       side,
            "price":      result.get("price"),
            "amount":     result.get("amount"),
            "pnl":        pnl,
            "signal":     signal,
            "confidence": confidence,
            "paper":      self.cfg.paper_trading,
        }
        with open(f"logs/trades_{safe_symbol}.jsonl", "a") as f:
            f.write(json.dumps(record) + "\n")

    def _save_trade_result(self, side: str, result: dict, requested_price: float,
                           pnl: float = None, pnl_pct: float = None,
                           signal: str = None, confidence: int = None,
                           mae: float = None, mfe: float = None):
        executed_price = float(result.get("price") or requested_price)
        slippage = None
        if requested_price:
            slippage = (executed_price - requested_price) / requested_price * 100
            if side == "SELL":
                slippage *= -1
        loss_type = classify_loss(
            pnl_pct=pnl_pct,
            signal=signal,
            mae=mae,
            mfe=mfe,
            slippage=slippage,
            fee=_float_or_none(result.get("fee")),
        )
        self.storage.save_trade_result(
            TradeResult(
                symbol=self.cfg.symbol,
                strategy_id="trend_following",
                strategy_version=self.cfg.strategy_version,
                side=side,
                timestamp=datetime.utcnow(),
                price=executed_price,
                amount=float(result.get("amount") or 0.0),
                cost=_float_or_none(result.get("cost") or result.get("gross")),
                order_id=result.get("order_id"),
                signal=signal,
                confidence=confidence,
                pnl=pnl,
                pnl_pct=pnl_pct,
                slippage=slippage,
                mae=mae,
                mfe=mfe,
                fee=_float_or_none(result.get("fee")),
                loss_type=loss_type,
                paper=self.cfg.paper_trading,
                details=result,
            )
        )

    def _save_market_state(self, df, ind, timestamp: datetime):
        last = df.iloc[-1]
        self.storage.save_market_snapshot(
            MarketSnapshot(
                symbol=self.cfg.symbol,
                timeframe=self.cfg.timeframe,
                timestamp=timestamp,
                open=float(last["open"]),
                high=float(last["high"]),
                low=float(last["low"]),
                close=float(last["close"]),
                volume=float(last["volume"]),
                indicators=self._indicator_payload(ind),
            )
        )
        self.storage.save_regime_record(
            RegimeRecord(
                symbol=self.cfg.symbol,
                timeframe=self.cfg.timeframe,
                timestamp=timestamp,
                regime=ind.regime.value,
                confidence=ind.confidence,
                atr=ind.atr,
                atr_pct=ind.atr_pct,
                hv=ind.hv,
                adx=ind.adx,
                volume_ratio=ind.volume_ratio,
                breakout_score=ind.breakout_score,
            )
        )

    def _save_entry_context(self, timestamp: datetime, signal: Signal, price: float,
                            ind, mtf_bias: str, strategy_return_pct: float,
                            setup: dict | None = None):
        self.storage.save_entry_context(
            EntryContext(
                symbol=self.cfg.symbol,
                timeframe=self.cfg.timeframe,
                timestamp=timestamp,
                strategy_id="trend_following",
                strategy_version=self.cfg.strategy_version,
                signal=signal.value,
                price=price,
                confidence=ind.confidence,
                regime=ind.regime.value,
                mtf_bias=mtf_bias,
                strategy_return_pct=strategy_return_pct,
                context={**self._indicator_payload(ind), **(setup or {})},
            )
        )

    def _save_signal_decision(self, timestamp: datetime, signal: Signal, price: float,
                              ind, accepted: bool, reason: str, mtf_bias: str,
                              strategy_return_pct: float, setup: dict | None = None):
        self.storage.save_signal_decision(
            SignalDecision(
                run_id=self.run_id,
                symbol=self.cfg.symbol,
                timeframe=self.cfg.timeframe,
                timestamp=timestamp,
                strategy_id="trend_following",
                strategy_version=self.cfg.strategy_version,
                signal=signal.value,
                accepted=accepted,
                reason=reason,
                price=price,
                confidence=ind.confidence,
                regime=ind.regime.value,
                mtf_bias=mtf_bias,
                strategy_return_pct=strategy_return_pct,
                setup_score=(setup or {}).get("setup_score"),
                setup_quality=(setup or {}).get("setup_quality"),
                context=self._indicator_payload(ind),
            )
        )

    def _save_bot_error(self, source: str, exc: Exception):
        self.storage.save_bot_error(
            BotError(
                run_id=self.run_id,
                timestamp=datetime.utcnow(),
                source=source,
                message=str(exc),
                error_type=type(exc).__name__,
                traceback=traceback.format_exc(),
                context={
                    "symbol": self.cfg.symbol,
                    "timeframe": self.cfg.timeframe,
                    "in_position": self.in_position,
                },
            )
        )

    def _save_equity_point(self, timestamp: datetime, price: float,
                           quote_free: float, equity: float):
        self.storage.save_equity_point(
            EquityPoint(
                symbol=self.cfg.symbol,
                timeframe=self.cfg.timeframe,
                timestamp=timestamp,
                equity=equity,
                quote_balance=quote_free,
                base_amount=self.position_size if self.in_position else 0.0,
                mark_price=price,
                realized_pnl=self.total_pnl,
                paper=self.cfg.paper_trading,
            )
        )
        if self.in_position:
            self._save_open_position_state(quote_balance=quote_free)

    def _open_shadow_trade(self, timestamp: datetime, signal: Signal, price: float,
                           ind, mtf_bias: str, setup: dict):
        if not self.cfg.shadow_live_enabled:
            return
        self.storage.save_shadow_trade(
            ShadowTrade(
                run_id=self.run_id,
                symbol=self.cfg.symbol,
                timeframe=self.cfg.timeframe,
                strategy_id="trend_following",
                strategy_version=self.cfg.strategy_version,
                entry_timestamp=timestamp,
                entry_price=price,
                stop_price=price * (1 - self.cfg.stop_loss_pct / 100),
                take_profit_price=price * (1 + self.cfg.take_profit_pct / 100),
                signal=signal.value,
                confidence=ind.confidence,
                setup_score=setup.get("setup_score"),
                setup_quality=setup.get("setup_quality"),
                regime=ind.regime.value,
                mtf_bias=mtf_bias,
                metadata=self._indicator_payload(ind),
            )
        )

    def _update_shadow_trades(self, df, timestamp: datetime):
        if not self.cfg.shadow_live_enabled:
            return
        try:
            last = df.iloc[-1]
            high = float(last["high"])
            low = float(last["low"])
            close = float(last["close"])
            for trade in self.storage.fetch_open_shadow_trades(
                symbol=self.cfg.symbol,
                timeframe=self.cfg.timeframe,
            ):
                entry = float(trade.get("entry_price") or 0.0)
                if entry <= 0:
                    continue
                exit_price = None
                exit_reason = None
                if low <= float(trade.get("stop_price") or 0.0):
                    exit_price = float(trade["stop_price"])
                    exit_reason = "stop_loss"
                elif high >= float(trade.get("take_profit_price") or 0.0):
                    exit_price = float(trade["take_profit_price"])
                    exit_reason = "take_profit"
                if exit_price is None:
                    continue
                pnl_pct = (exit_price - entry) / entry * 100
                self.storage.close_shadow_trade(
                    int(trade["id"]),
                    exit_timestamp=timestamp,
                    exit_price=exit_price or close,
                    exit_reason=exit_reason,
                    pnl_pct=pnl_pct,
                )
        except Exception as exc:
            self.logger.warning(f"Falha ao atualizar shadow live: {exc}")

    def _update_position_extremes(self, price: float):
        self.position_low = price if self.position_low is None else min(self.position_low, price)
        self.position_high = price if self.position_high is None else max(self.position_high, price)

    def _mae_mfe(self) -> tuple[Optional[float], Optional[float]]:
        if not self.buy_price:
            return None, None
        mae = None if self.position_low is None else ((self.position_low - self.buy_price) / self.buy_price) * 100
        mfe = None if self.position_high is None else ((self.position_high - self.buy_price) / self.buy_price) * 100
        return mae, mfe

    @staticmethod
    def _last_candle_time(df) -> datetime:
        idx = df.index[-1]
        if hasattr(idx, "to_pydatetime"):
            return idx.to_pydatetime()
        return datetime.utcnow()

    @staticmethod
    def _indicator_payload(ind) -> dict:
        payload = asdict(ind)
        regime = payload.get("regime")
        if hasattr(regime, "value"):
            payload["regime"] = regime.value
        return payload

    def _save_open_position_state(self, quote_balance: float | None = None):
        if not self.in_position:
            return
        self.storage.save_open_position_state(
            OpenPositionState(
                symbol=self.cfg.symbol,
                strategy_id="trend_following",
                timestamp=datetime.utcnow(),
                in_position=self.in_position,
                buy_price=self.buy_price,
                amount=self.position_size,
                entry_confidence=self.entry_confidence,
                position_low=self.position_low,
                position_high=self.position_high,
                trailing_stop_price=self.trailing_stop.stop_price if self.trailing_stop else None,
                trailing_highest_price=self.trailing_stop.highest_price if self.trailing_stop else None,
                trailing_activated=self.trailing_stop.activated if self.trailing_stop else False,
                quote_balance=quote_balance,
                base_amount=self.position_size,
                paper=self.cfg.paper_trading,
                metadata={"strategy_version": self.cfg.strategy_version},
            )
        )

    def _restore_open_position_state(self):
        state = self.storage.load_open_position_state(self.cfg.symbol, "trend_following")
        if not state or not state.get("in_position"):
            return

        amount = float(state.get("amount") or 0.0)
        buy_price = state.get("buy_price")
        if amount <= 0 or buy_price is None:
            return

        self.in_position = True
        self.buy_price = float(buy_price)
        self.position_size = amount
        self.entry_confidence = int(state.get("entry_confidence") or 0)
        self.position_low = _float_or_none(state.get("position_low"))
        self.position_high = _float_or_none(state.get("position_high"))

        self.trailing_stop = TrailingStop(
            buy_price=self.buy_price,
            trail_pct=self.cfg.stop_loss_pct,
            activate_pct=1.0,
        )
        if state.get("trailing_highest_price") is not None:
            self.trailing_stop._highest_price = float(state["trailing_highest_price"])
        if state.get("trailing_stop_price") is not None:
            self.trailing_stop._stop_price = float(state["trailing_stop_price"])
        self.trailing_stop._activated = bool(state.get("trailing_activated"))

        self.connector.restore_paper_state(
            state.get("quote_balance"),
            state.get("base_amount") or amount,
            self.buy_price,
        )
        self.logger.warning(
            f"Estado de posicao restaurado do storage: "
            f"{self.cfg.symbol} qty={self.position_size:.8f} entrada=${self.buy_price:,.2f}"
        )
        self._restored_position_state = True

    def _reconcile_restored_position(self, balances: dict):
        if not self._restored_position_state or not self.in_position:
            return
        base = balances.get("base") if balances else None
        if base is None:
            self.logger.warning("Nao foi possivel reconciliar posicao restaurada: saldo base indisponivel.")
            return
        base = float(base)
        if base + 1e-12 < self.position_size * 0.95:
            msg = (
                f"Posicao restaurada diverge do saldo: storage={self.position_size:.8f}, "
                f"saldo_base={base:.8f}. Mantendo bot em posicao para evitar dupla compra."
            )
            self.logger.error(msg)
            self.storage.save_bot_error(
                BotError(
                    run_id=self.run_id,
                    timestamp=datetime.utcnow(),
                    source="position_reconciliation",
                    message=msg,
                    error_type="StateMismatch",
                    context={"storage_amount": self.position_size, "base_balance": base},
                )
            )

    async def shutdown(self):
        self.running = False
        bal = await self.connector.get_balances()
        qc = self.cfg.quote_currency
        summary = (
            f"⏹  Bot encerrado\n"
            f"   Trades: {self.total_trades} | Win rate: {self._win_rate()}%\n"
            f"   P&L total: {self.total_pnl:+.2f} {qc}\n"
            f"   P&L hoje:  {self.pnl_today:+.2f} {qc}\n"
            f"   Saldo {qc}: {self._quote_free(bal):.2f}"
        )
        self.logger.info(summary)
        await self.notifier.send(summary)
        self.storage.finish_bot_run(self.run_id, "stopped")
        self.storage.close()
        await self.connector.close()


def _float_or_none(value):
    if value is None:
        return None
    return float(value)
