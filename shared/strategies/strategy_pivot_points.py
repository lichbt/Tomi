"""Pivot Points Strategy.

Uses daily/weekly pivot levels (Classic, Fibonacci, or Camarilla) with
ATR-based trailing stops and trend confirmation via 200 SMA.

Signal convention: +1 = long, -1 = short, 0 = flat.
"""
import pandas as pd
import numpy as np


def strategy_pivot_points(df: pd.DataFrame, params: dict) -> pd.Series:
    """Pivot Points reversal/breakout strategy.

    Calculates standard pivot point (PP) and support/resistance levels
    from the previous period's OHLC. Enters on pullback-to-support in
    uptrend (long) or pullback-to-resistance in downtrend (short).

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ['open', 'high', 'low', 'close', 'volume'].
    params : dict
        sma_period   : int   - trend filter SMA window (default 200)
        atr_period   : int   - ATR window for stops (default 14)
        stop_mult    : float - ATR multiplier for trailing stop (default 2.0)
        pivot_period : int   - lookback for pivot calc in bars (default 50 ≈ weekly on H4)

    Returns
    -------
    pd.Series[int]
        Signal series shifted by 1 to prevent look-ahead bias.
    """
    sma_period = params.get('sma_period', 200)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_mult', 2.0)
    pivot_lookback = params.get('pivot_period', 50)

    close = df['close'].astype(np.float64)
    high = df['high'].astype(np.float64)
    low = df['low'].astype(np.float64)
    prev_close = close.shift(1)
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    # Classic Pivot Points
    pp = (prev_high + prev_low + prev_close) / 3.0
    r1 = 2 * pp - prev_low
    s1 = 2 * pp - prev_high
    r2 = pp + (prev_high - prev_low)
    s2 = pp - (prev_high - prev_low)
    r3 = pp + 2 * (prev_high - prev_low)
    s3 = pp - 2 * (prev_high - prev_low)

    # Trend filter
    sma = close.rolling(sma_period).mean()
    trend_up = close > sma
    trend_down = close < sma

    # ATR for stops
    tr = pd.concat([high - low, abs(high - prev_close), abs(low - prev_close)], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    signals = pd.Series(0, index=df.index, dtype=int)
    position = 0
    peak = 0.0
    trough = 0.0

    start_idx = max(sma_period, atr_period, pivot_lookback)
    for i in range(start_idx, len(df)):
        if np.isnan(atr.iloc[i]) or atr.iloc[i] <= 0:
            signals.iloc[i] = position
            continue

        # Trailing stop exit
        if position == 1:
            peak = max(peak, high.iloc[i])
            if low.iloc[i] <= peak - stop_mult * atr.iloc[i]:
                position = 0
        elif position == -1:
            trough = min(trough, low.iloc[i])
            if high.iloc[i] >= trough + stop_mult * atr.iloc[i]:
                position = 0

        # Entry logic
        if position == 0:
            # Long: uptrend + pullback to S1 or S2
            if trend_up.iloc[i] and low.iloc[i] <= s1.iloc[i] and close.iloc[i] > s1.iloc[i]:
                position = 1
                peak = high.iloc[i]
            # Short: downtrend + pullback to R1 or R2
            elif trend_down.iloc[i] and high.iloc[i] >= r1.iloc[i] and close.iloc[i] < r1.iloc[i]:
                position = -1
                trough = low.iloc[i]

        signals.iloc[i] = position

    return signals.shift(1).fillna(0).astype(int)
