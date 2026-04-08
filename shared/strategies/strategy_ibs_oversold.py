# Strategy: Oversold Intraday Mean Reversion (adapted for H4/Daily)
# Author: Strategy Coder Agent
# Source: algomatictrading.com — 42.2% WR, 2162 trades, MAR 0.47 on DAX 1H
# Edge: IBS + RSI2 double oversold in low-volatility regime, clean bounce
# Libraries: pandas, numpy only

import pandas as pd
import numpy as np
from typing import Dict


def strategy_ibs_oversold(
    df: pd.DataFrame,
    params: Dict[str, any]
) -> pd.Series:
    """
    IBS RSI Mean Reversion with Low Volatility Filter.

    Internal Bar Strength (IBS) = (Close - Low) / (High - Low)
    IBS near 0 = price closed near the low (bearish/bottom)
    IBS near 1 = price closed near the high (bullish/top)

    Entry Long (long only — indices bounce better than crash):
      1. IBS < ibs_threshold (price closed near low of bar)
      2. RSI2 < rsi_threshold (very short-term oversold)
      3. Bollinger Bandwidth < bb_width (volatility is compressed)

    Exit:
      1. Low > previous close (gap-up confirmation)
      2. OR bars_held > max_hold

    Args:
        df: OHLCV DataFrame
        params: {
            'ibs_threshold': float (default 0.10),     # IBS threshold
            'rsi_period': int (default 2),             # RSI period (very short)
            'rsi_threshold': float (default 10),       # RSI oversold level
            'bb_period': int (default 50),             # Bollinger Band lookback
            'bb_width': float (default 0.06),          # Max BB bandwidth for entry
            'atr_period': int (default 14),
            'stop_atr_mult': float (default 3.0),
            'max_hold': int (default 10),
        }

    Returns:
        pd.Series: +1 (long), 0 (flat). Long-only.
    """
    required = {'open', 'high', 'low', 'close', 'volume'}
    if not required.issubset(df.columns):
        raise ValueError(f'Missing columns: {required - set(df.columns)}')

    ibs_threshold = params.get('ibs_threshold', 0.10)
    rsi_period = params.get('rsi_period', 2)
    rsi_threshold = params.get('rsi_threshold', 10)
    bb_period = params.get('bb_period', 50)
    bb_width = params.get('bb_width', 0.06)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 3.0)
    max_hold = params.get('max_hold', 10)

    close = df['close']
    open_ = df['open']
    high = df['high']
    low = df['low']

    # ── IBS: (Close - Low) / (High - Low) ──
    ibs_range = high - low
    ibs = (close - low) / (ibs_range + 1e-9)

    # ── RSI2: Very short-term RSI ──
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(rsi_period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(rsi_period).mean()
    rs = gain / (loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))

    # ── Bollinger Bandwidth ──
    sma = close.rolling(bb_period).mean()
    std = close.rolling(bb_period).std(ddof=0)
    upper = sma + 2 * std
    lower = sma - 2 * std
    bandwidth = (upper - lower) / (sma + 1e-9)

    # ── ATR for stop ──
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    # ── Position-holding ──
    signals = pd.Series(0, index=df.index, dtype=np.int8)
    position = 0
    entry_bar = 0
    bars_held = 0
    atr_stop = 0.0

    for i in range(max(bb_period, rsi_period, atr_period), len(df)):
        if position == 1:
            bars_held += 1

            # Exit: gap-up confirmation
            if low.iloc[i] > close.iloc[i - 1]:
                position = 0
            # Exit: trailing ATR stop
            elif low.iloc[i] <= atr_stop:
                position = 0
            # Exit: max_hold
            elif bars_held >= max_hold:
                position = 0
        else:
            # Entry: triple oversold
            if (ibs.iloc[i] < ibs_threshold and
                rsi.iloc[i] < rsi_threshold and
                bandwidth.iloc[i] < bb_width):
                position = 1
                entry_bar = i
                bars_held = 0
                atr_stop = low.iloc[i] - atr.iloc[i] * stop_mult

        signals.iloc[i] = position

    return signals.shift(1).fillna(0).astype(int)
