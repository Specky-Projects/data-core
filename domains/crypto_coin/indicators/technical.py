"""
Indicadores técnicos v3 — Fase 4: ATR, VWAP, volatilidade, breakout quality,
multi-signal scoring.

Novos em v3:
  - ATR  (Average True Range) — volatilidade em termos de preço
  - ATR% — ATR como % do preço atual (normalizado)
  - VWAP — preço médio ponderado por volume (filtro de tendência intraday)
  - HV   — volatilidade histórica anualizada (desvio dos log-retornos)
  - BB Width — largura das Bollinger Bands como % (mede compressão)
  - ATR Momentum — ATR curto vs longo (expansão = momentum, compressão = pausa)
  - Breakout Score (0-100) — qualidade da entrada: combina distância da BB,
      RSI, volume, ATR e candle body
  - Confidence Score refatorado: agora inclui todos os novos fatores
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum

import numpy as np
import pandas as pd


class MarketRegime(Enum):
    TRENDING_UP   = "tendência de alta"
    TRENDING_DOWN = "tendência de baixa"
    RANGING       = "mercado lateral"
    UNKNOWN       = "indefinido"


@dataclass
class Indicators:
    close: float

    # Médias móveis
    ma_fast: Optional[float] = None
    ma_slow: Optional[float] = None

    # RSI
    rsi: Optional[float] = None

    # Bollinger Bands
    bb_upper: Optional[float] = None
    bb_mid:   Optional[float] = None
    bb_lower: Optional[float] = None
    bb_width: Optional[float] = None   # (upper-lower)/mid * 100 — compressão/expansão

    # Volume
    volume_ratio:   Optional[float] = None
    volume_confirm: bool = False
    volume_trend:   str  = "neutral"   # "rising" | "falling" | "neutral"

    # ADX
    adx: Optional[float] = None

    # ATR — novos em v3
    atr:     Optional[float] = None    # valor absoluto
    atr_pct: Optional[float] = None    # ATR / close * 100

    # ATR Momentum: ATR(fast) / ATR(slow) — >1.1 = expandindo, <0.9 = comprimindo
    atr_momentum: Optional[float] = None

    # VWAP — novos em v3
    vwap:         Optional[float] = None
    price_above_vwap: bool = False

    # Volatilidade histórica anualizada — novos em v3
    hv: Optional[float] = None         # % anualizado

    # Breakout quality score (0-100) — novos em v3
    breakout_score: float = 0.0

    # Regime e B&H
    regime:          MarketRegime    = MarketRegime.UNKNOWN
    buy_and_hold_pct: Optional[float] = None

    # Score de confiança (0-100)
    confidence: int = 0

    # Sinais derivados (booleans)
    ma_cross_bull:  bool = False
    ma_cross_bear:  bool = False
    rsi_oversold:   bool = False
    rsi_overbought: bool = False
    price_below_bb: bool = False
    price_above_bb: bool = False


# ── Indicadores base ──────────────────────────────────────────

def sma(series: pd.Series, period) -> pd.Series:
    return series.rolling(window=int(period)).mean()


def ema(series: pd.Series, period) -> pd.Series:
    return series.ewm(span=int(period), adjust=False).mean()


def calc_rsi(series: pd.Series, period) -> pd.Series:
    period = int(period)
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_bollinger(series: pd.Series, period, std_dev: float):
    period = int(period)
    mid = sma(series, period)
    std = series.rolling(window=period).std()
    return mid + std_dev * std, mid, mid - std_dev * std


def calc_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high  = df["high"].astype(float)
    low   = df["low"].astype(float)
    close = df["close"].astype(float)

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)

    dm_pos = high.diff().clip(lower=0)
    dm_neg = (-low.diff()).clip(lower=0)
    dm_pos = dm_pos.where(dm_pos > dm_neg, 0)
    dm_neg = dm_neg.where(dm_neg > dm_pos, 0)

    atr    = tr.ewm(span=period, adjust=False).mean()
    di_pos = 100 * dm_pos.ewm(span=period, adjust=False).mean() / atr.replace(0, np.nan)
    di_neg = 100 * dm_neg.ewm(span=period, adjust=False).mean() / atr.replace(0, np.nan)
    dx     = 100 * (di_pos - di_neg).abs() / (di_pos + di_neg).replace(0, np.nan)
    return dx.ewm(span=period, adjust=False).mean()


def calc_volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.Series:
    vol = df["volume"].astype(float)
    avg = vol.rolling(window=period).mean()
    return vol / avg.replace(0, np.nan)


# ── Novos indicadores v3 ──────────────────────────────────────

def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    high  = df["high"].astype(float)
    low   = df["low"].astype(float)
    close = df["close"].astype(float)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def calc_vwap(df: pd.DataFrame) -> Optional[float]:
    """
    VWAP simplificado sobre a janela disponível.
    Em produção normalmente reseta a cada sessão/dia;
    aqui usamos a janela de cálculo inteira (suficiente para filtro de tendência).
    """
    try:
        vol     = df["volume"].astype(float)
        typical = (df["high"].astype(float) + df["low"].astype(float)
                   + df["close"].astype(float)) / 3
        total_vol = vol.sum()
        if total_vol == 0:
            return None
        return float((typical * vol).sum() / total_vol)
    except Exception:
        return None


def calc_hv(close: pd.Series, period: int = 20, timeframe: str = "15m") -> pd.Series:
    """
    Volatilidade histórica anualizada (desvio padrão dos log-retornos).
    Fator de anualização depende do timeframe.
    """
    tf_to_periods = {
        "1m": 525600, "3m": 175200, "5m": 105120, "15m": 35040,
        "30m": 17520,  "1h": 8760,  "4h": 2190,   "1d": 365,
    }
    ann = tf_to_periods.get(timeframe, 35040)
    log_ret = np.log(close / close.shift(1))
    return log_ret.rolling(period).std() * np.sqrt(ann) * 100


def calc_volume_trend(df: pd.DataFrame, fast: int = 5, slow: int = 20) -> str:
    """Classifica tendência do volume: rising / falling / neutral."""
    vol = df["volume"].astype(float)
    if len(vol) < slow:
        return "neutral"
    avg_fast = vol.iloc[-fast:].mean()
    avg_slow = vol.iloc[-slow:].mean()
    if avg_slow == 0:
        return "neutral"
    ratio = avg_fast / avg_slow
    if ratio > 1.2:
        return "rising"
    if ratio < 0.8:
        return "falling"
    return "neutral"


def calc_breakout_score(ind: "Indicators", df: pd.DataFrame, rsi_oversold: float = 35.0) -> float:
    """
    Qualidade do breakout / entrada (0-100).

    Fatores:
      1. Distância abaixo da BB inferior (em múltiplos de ATR)  — 0-30 pts
      2. RSI abaixo do oversold + profundidade                   — 0-25 pts
      3. Volume ratio                                            — 0-20 pts
      4. ATR momentum (expansão = movimento real)                — 0-15 pts
      5. Candle body vs ATR (corpo grande = direcional)          — 0-10 pts
    """
    score = 0.0

    # 1. Preço vs BB inferior
    if ind.bb_lower and ind.atr and ind.atr > 0:
        dist = (ind.bb_lower - ind.close) / ind.atr   # negativo = abaixo da BB
        if dist > 0:      # preço abaixo da BB inferior
            score += min(30, dist * 15)
        elif dist > -0.5: # perto da BB inferior
            score += 8

    # 2. RSI profundidade abaixo do oversold
    if ind.rsi is not None:
        depth = rsi_oversold - ind.rsi
        if depth > 0:
            score += min(25, depth * 1.5)
        elif depth > -5:
            score += 5

    # 3. Volume ratio
    if ind.volume_ratio:
        if ind.volume_ratio >= 2.0:   score += 20
        elif ind.volume_ratio >= 1.5: score += 14
        elif ind.volume_ratio >= 1.2: score += 8
        elif ind.volume_ratio >= 1.0: score += 3

    # 4. ATR momentum (expansão)
    if ind.atr_momentum:
        if ind.atr_momentum >= 1.2:   score += 15
        elif ind.atr_momentum >= 1.05: score += 8
        elif ind.atr_momentum < 0.85:  score -= 5   # compressão = penaliza

    # 5. Corpo do último candle vs ATR
    if len(df) >= 1 and ind.atr and ind.atr > 0:
        last = df.iloc[-1]
        body = abs(float(last["close"]) - float(last["open"]))
        ratio = body / ind.atr
        if ratio >= 0.5:   score += 10
        elif ratio >= 0.25: score += 5

    return max(0.0, min(100.0, score))


# ── Score de confiança v3 ─────────────────────────────────────

def calc_confidence(ind: "Indicators", cfg) -> int:
    """
    Score de confiança 0-100 para um sinal de COMPRA.
    v3: inclui ATR, breakout_score, VWAP, HV e volume trend.
    """
    score = 0

    # RSI sobrevendido (0-25 pts)
    if ind.rsi is not None:
        if ind.rsi < cfg.rsi_oversold:
            score += 25
        elif ind.rsi < cfg.rsi_oversold + 8:
            score += 12

    # Cruzamento de MA (0-20 pts)
    if ind.ma_cross_bull:
        score += 20
    elif ind.ma_fast and ind.ma_slow and ind.ma_fast > ind.ma_slow:
        score += 8

    # Volume confirma (0-15 pts)
    if ind.volume_confirm:
        score += 15
    elif ind.volume_ratio and ind.volume_ratio > 1.0:
        score += 6
    if ind.volume_trend == "rising":
        score += 5

    # Bollinger abaixo (0-12 pts)
    if ind.price_below_bb:
        score += 12
    elif ind.bb_lower and ind.close < ind.bb_mid:
        score += 4

    # ADX — força da tendência (0-8 pts)
    if ind.adx:
        if ind.adx > 30:   score += 8
        elif ind.adx > 25: score += 5
        elif ind.adx > 20: score += 2

    # ATR momentum — expansão = movimento real (0-10 pts, penaliza compressão)
    if ind.atr_momentum:
        if ind.atr_momentum >= 1.15: score += 10
        elif ind.atr_momentum >= 1.0: score += 4
        elif ind.atr_momentum < 0.85: score -= 8

    # VWAP — preço abaixo do VWAP = mais barato que a média do período (0-5 pts)
    if ind.vwap and ind.close < ind.vwap:
        score += 5

    # Breakout score contribui diretamente (0-15 pts escalonados)
    score += int(ind.breakout_score * 0.15)

    # Penaliza alta volatilidade (HV > 120% anual = mercado errático)
    if ind.hv and ind.hv > 120:
        score -= 10

    return max(0, min(score, 100))


# ── Regime ────────────────────────────────────────────────────

def detect_regime(adx: float, ma_fast: float, ma_slow: float) -> MarketRegime:
    if adx is None:
        return MarketRegime.UNKNOWN
    if adx > 25:
        return MarketRegime.TRENDING_UP if ma_fast >= ma_slow else MarketRegime.TRENDING_DOWN
    if adx < 20:
        return MarketRegime.RANGING
    return MarketRegime.UNKNOWN


# ── Função principal ──────────────────────────────────────────

def compute_indicators(df: pd.DataFrame, cfg) -> Optional[Indicators]:
    """
    Recebe DataFrame com colunas open/high/low/close/volume e retorna
    Indicators com todos os valores calculados no último candle.
    """
    atr_period = getattr(cfg, "atr_period", 14)
    min_len    = max(cfg.ma_slow, cfg.rsi_period, cfg.bb_period, atr_period, 28) + 5
    if df is None or len(df) < min_len:
        return None

    close   = df["close"].astype(float)
    has_hlv = {"high", "low", "volume"}.issubset(df.columns)

    ma_f = sma(close, cfg.ma_fast)
    ma_s = sma(close, cfg.ma_slow)
    rsi  = calc_rsi(close, cfg.rsi_period)
    bb_upper, bb_mid, bb_lower = calc_bollinger(close, cfg.bb_period, cfg.bb_std)

    cur      = close.iloc[-1]
    cur_maf  = ma_f.iloc[-1]
    cur_mas  = ma_s.iloc[-1]
    prev_maf = ma_f.iloc[-2]
    prev_mas = ma_s.iloc[-2]

    ind = Indicators(close=float(cur))

    def _f(v):
        try:
            return float(v) if not np.isnan(v) else None
        except Exception:
            return None

    ind.ma_fast  = _f(cur_maf)
    ind.ma_slow  = _f(cur_mas)
    ind.rsi      = _f(rsi.iloc[-1])
    ind.bb_upper = _f(bb_upper.iloc[-1])
    ind.bb_mid   = _f(bb_mid.iloc[-1])
    ind.bb_lower = _f(bb_lower.iloc[-1])

    # BB Width
    if ind.bb_upper and ind.bb_lower and ind.bb_mid and ind.bb_mid > 0:
        ind.bb_width = round((ind.bb_upper - ind.bb_lower) / ind.bb_mid * 100, 2)

    # Cruzamentos de MA
    if ind.ma_fast and ind.ma_slow:
        ind.ma_cross_bull = (prev_maf < prev_mas) and (cur_maf >= cur_mas)
        ind.ma_cross_bear = (prev_maf > prev_mas) and (cur_maf <= cur_mas)

    # RSI sinais
    if ind.rsi:
        ind.rsi_oversold   = ind.rsi < cfg.rsi_oversold
        ind.rsi_overbought = ind.rsi > cfg.rsi_overbought

    # Bollinger sinais
    if ind.bb_upper and ind.bb_lower:
        ind.price_below_bb = cur < ind.bb_lower
        ind.price_above_bb = cur > ind.bb_upper

    if has_hlv:
        # Volume
        vol_ratio = calc_volume_ratio(df, 20)
        ind.volume_ratio   = _f(vol_ratio.iloc[-1])
        ind.volume_confirm = bool(ind.volume_ratio and ind.volume_ratio > 1.3)
        ind.volume_trend   = calc_volume_trend(df)

        # ADX
        adx_series = calc_adx(df, 14)
        ind.adx = _f(adx_series.iloc[-1])

        # ATR
        atr_series = calc_atr(df, atr_period)
        ind.atr = _f(atr_series.iloc[-1])
        if ind.atr and cur > 0:
            ind.atr_pct = round(ind.atr / float(cur) * 100, 3)

        # ATR Momentum (fast/slow)
        if len(df) >= atr_period * 3:
            atr_fast = _f(calc_atr(df, max(7, atr_period // 2)).iloc[-1])
            atr_slow = _f(calc_atr(df, atr_period * 2).iloc[-1])
            if atr_fast and atr_slow and atr_slow > 0:
                ind.atr_momentum = round(atr_fast / atr_slow, 3)

        # VWAP
        ind.vwap = calc_vwap(df)
        if ind.vwap:
            ind.price_above_vwap = float(cur) > ind.vwap

        # Historical Volatility
        tf = getattr(cfg, "timeframe", "15m")
        hv_series = calc_hv(close, 20, tf)
        ind.hv = _f(hv_series.iloc[-1])

    # Regime
    if ind.adx and ind.ma_fast and ind.ma_slow:
        ind.regime = detect_regime(ind.adx, ind.ma_fast, ind.ma_slow)

    # Buy & Hold
    first_close = float(close.iloc[0])
    if first_close > 0:
        ind.buy_and_hold_pct = round(((float(cur) - first_close) / first_close) * 100, 2)

    # Breakout score (precisa de ATR calculado)
    if has_hlv:
        ind.breakout_score = calc_breakout_score(ind, df, rsi_oversold=cfg.rsi_oversold)

    # Confidence score
    ind.confidence = calc_confidence(ind, cfg)

    return ind
