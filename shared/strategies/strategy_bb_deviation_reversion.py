# Strategy: Bollinger Deviation Channel Mean Reversion
# Author: Strategy Coder Agent
# Edge: Statistical extremes (2-3 SD from mean) + RSI + candlestick reversal confirmation
# Libraries: pandas, numpy only

import pandas as pd
import numpy as np
from typing import Dict


def strategy_bb_deviation_reversion(
    df: pd.DataFrame,
    params: Dict[str, any]
) -> pd.Series:
    """
    Bollinger Deviation Channel Mean Reversion (optimized).

    Logic:
      1. Price wicks below lower band (2.5 SD), closes back inside, RSI < 25
      2. Long entry after confirmation
      3. Exit at ATR trailing stop (default 2.5x)

    Args:
        df: OHLCV DataFrame
        params: {'bb_period':int, 'bb_std_extreme':float, 'bb_std_exit':float,
                 'rsi_period':int, 'rsi_extreme':float, 'atr_period':int,
                 'stop_atr_mult':float}

    Returns:
        pd.Series: +1 (long), -1 (short), 0 (flat)
    """
    required = {'open', 'high', 'low', 'close', 'volume'}
    if not required.issubset(df.columns):
        raise ValueError(f'Missing columns: {required - set(df.columns)}')

    bb_period = params.get('bb_period', 20)
    bb_std_extreme = params.get('bb_std_extreme', 2.5)
    bb_std_exit = params.get('bb_std_exit', 1.0)
    rsi_period = params.get('rsi_period', 14)
    rsi_extreme = params.get('rsi_extreme', 25)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 2.5)

    # ── Convert to numpy arrays (fast) ──
    close = df['close'].values.astype(np.float64)
    high = df['high'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)

    n = len(close)
    signals = np.zeros(n, dtype=np.int8)

    # ── Bollinger Bands ──
    sma = pd.Series(close).rolling(bb_period).mean().values
    std = pd.Series(close).rolling(bb_period).std(ddof=0).values
    lower_extreme = sma - bb_std_extreme * std
    upper_extreme = sma + bb_std_extreme * std

    # ── RSI ──
    delta = np.diff(close, prepend=close[0])
    gain = pd.Series(delta).where(delta > 0, 0.0).rolling(rsi_period).mean()
    loss = pd.Series(-delta).where(delta < 0, 0.0).rolling(rsi_period).mean()
    rs = gain / (loss + 1e-9)
    rsi = (100 - (100 / (1 + rs))).values

    # ── ATR ──
    tr_high = high - low
    tr_hc = np.abs(high - np.append(0, close[:-1]))
    tr_lc = np.abs(low - np.append(0, close[:-1]))
    tr = np.maximum(np.maximum(tr_high, tr_hc), tr_lc)
    atr = pd.Series(tr).rolling(atr_period).mean().values

    # ── Position holding loop (optimized with arrays) ──
    position = 0
    peak = 0.0
    trough = 0.0

    for i in range(bb_period + atr_period + 2, n):
        if position == 1:
            if high[i] > peak:
                peak = high[i]
            if low[i] <= peak - atr[i] * stop_mult or close[i] > upper_exit[i]:
                position = 0
            elif high[i-1] > upper_extreme[i-1] and close[i] < upper_extreme[i] and rsi[i] > (100 - rsi_extreme):
                position = -1
                trough = low[i]
        elif position == -1:
            if low[i] < trough:
                trough = low[i]
            if high[i] >= trough + atr[i] * stop_mult or close[i] < lower_exit[i]:
                position = 0
            elif low[i-1] < lower_extreme[i-1] and close[i] > lower_extreme[i] and rsi[i] < rsi_extreme:
                position = 1
                peak = high[i]
        else:
            if low[i-1] < lower_extreme[i-1] and close[i] > lower_extreme[i] and rsi[i] < rsi_extreme:
                position = 1
                peak = high[i]
            elif high[i-1] > upper_extreme[i-1] and close[i] < upper_extreme[i] and rsi[i] > (100 - rsi_extreme):
                position = -1
                trough = low[i]
        signals[i] = position

    # Shift by 1 for look-ahead bias prevention
    signals = np.append(0, signals[:-1])

    return pd.Series(signals, index=df.index, dtype=np.int8)
