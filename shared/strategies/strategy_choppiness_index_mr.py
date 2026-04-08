"""
Choppiness Index Mean Reversion Strategy

Entry Conditions:
- Long:  CHOP > 55, RSI < 45, ADX < 25
- Short: CHOP > 55, RSI > 55, ADX < 25

Exit Conditions:
- Long exit:  RSI > 55
- Short exit: RSI < 45

Notes:
- CHOP > 55 identifies choppy/ranging regime (not the textbook 61.8,
  which was too strict — RSI extremes rarely coincide with CHOP > 61.8)
- ADX < 25 ensures no strong trend (mean reversion fails in trends)
- RSI at 45/55 (not 30/70) captures mean reversion in ranging markets

All signals use .shift(1) to prevent look-ahead bias.
Pure pandas/numpy — no external dependencies.
"""

import pandas as pd
import numpy as np


def _true_range(high, low, close):
    """Calculate True Range."""
    prev_close = close.shift(1)
    h_l = high - low
    h_pc = (high - prev_close).abs()
    l_pc = (low - prev_close).abs()
    return pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)


def _rsi(close, period=14):
    """Calculate RSI using exponential moving average."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(high, low, close, period=14):
    """Calculate Average True Range."""
    tr = _true_range(high, low, close)
    return tr.rolling(window=period, min_periods=period).mean()


def _directional_movement(high, low, close, period=14):
    """Calculate ADX from scratch."""
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    plus_dm = ((high - prev_high) > (prev_low - low)).astype(float) * (high - prev_high)
    plus_dm = plus_dm.where(plus_dm > 0, 0.0).where(high > prev_high, 0.0)

    minus_dm = ((prev_low - low) > (high - prev_high)).astype(float) * (prev_low - low)
    minus_dm = minus_dm.where(minus_dm > 0, 0.0).where(prev_low > low, 0.0)

    atr = _atr(high, low, close, period)
    plus_di = 100.0 * plus_dm.ewm(alpha=1/period, adjust=False).mean() / (atr + 1e-10)
    minus_di = 100.0 * minus_dm.ewm(alpha=1/period, adjust=False).mean() / (atr + 1e-10)

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx


def strategy_choppiness_index_mr(df):
    """
    Generate trading signals for Choppiness Index Mean Reversion strategy.

    Args:
        df: DataFrame with columns ['high', 'low', 'close', 'volume']

    Returns:
        pd.Series with positions: 1 (long), -1 (short), 0 (flat)
    """
    required_cols = {'high', 'low', 'close', 'volume'}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Missing columns: {required_cols - set(df.columns)}")

    df = df.sort_index()
    high = df['high']
    low = df['low']
    close = df['close']
    N = 14  # Choppiness Index period

    # 1. Choppiness Index
    atr_sum = _true_range(high, low, close).rolling(N).sum()
    price_range = high.rolling(N).max() - low.rolling(N).min()
    chop = 100.0 * np.log10(atr_sum / (price_range + 1e-10) + 1e-10) / np.log10(N)
    chop = chop.clip(0, 100)

    # 2. RSI
    rsi = _rsi(close, 14)

    # 3. ADX (trend filter — only trade when ADX is low / no strong trend)
    adx = _directional_movement(high, low, close, 14)

    # --- Entry / Exit Conditions ---
    # Long: choppy regime (CHOP > 55) + oversold (RSI < 45) + no trend (ADX < 25)
    # Short: choppy regime (CHOP > 55) + overbought (RSI > 55) + no trend (ADX < 25)
    long_entry = (chop > 55) & (rsi < 45) & (adx < 25)
    short_entry = (chop > 55) & (rsi > 55) & (adx < 25)

    # Exit on mean reversion: RSI crosses back to center
    long_exit = rsi > 55
    short_exit = rsi < 45

    # --- Position Tracking ---
    signals = pd.Series(0, index=df.index, dtype=float)
    position = 0

    for i in range(len(df)):
        if position == 1:
            if pd.notna(long_exit.iloc[i]) and long_exit.iloc[i]:
                position = 0
        elif position == -1:
            if pd.notna(short_exit.iloc[i]) and short_exit.iloc[i]:
                position = 0

        if position == 0:
            if pd.notna(long_entry.iloc[i]) and long_entry.iloc[i]:
                position = 1
            elif pd.notna(short_entry.iloc[i]) and short_entry.iloc[i]:
                position = -1

        signals.iloc[i] = position

    # shift 1 bar to prevent lookahead bias
    return signals.shift(1).fillna(0)
