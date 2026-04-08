"""
Trend-Adjusted Mean Reversion for QQQ

Source: https://github.com/FrancescoBellingeri/Python-Algo-Trading-Suite
Indicators: SMA 200, Williams %R (10), ATR (14)
"""

import pandas as pd
import numpy as np

def ta_sma(series, period):
    return series.rolling(period).mean()

def ta_willr(high, low, close, period):
    """Williams %R: -100 to 0, oversold < -80, overbought > -20"""
    highest = high.rolling(period).max()
    lowest = low.rolling(period).min()
    return -100 * (highest - close) / (highest - lowest + 1e-9)

def ta_atr(high, low, close, period):
    tr = pd.concat([
        high - low,
        abs(high - close.shift(1)),
        abs(low - close.shift(1))
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def strategy_trendadjustedmeanreversion(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """
    Enter long when price > SMA200 AND Williams %R < -80.
    Long-only strategy with ATR-based stops.

    Parameters
    ----------
    df : pd.DataFrame with columns ['open','high','low','close','volume']
    params : dict, optional
        'sma_period' : default 200
        'willr_period' : default 10
        'atr_period' : default 14
        'stop_multiplier' : default 10 (ATR multiples for stop)

    Returns
    -------
    pd.Series : +1 (long), 0 (flat)
    """
    p = params or {}
    sma_period = p.get('sma_period', 200)
    willr_period = p.get('willr_period', 10)
    atr_period = p.get('atr_period', 14)
    stop_mult = p.get('stop_multiplier', 10)

    close = df['close']
    high = df['high']
    low = df['low']

    sma200 = ta_sma(close, sma_period)
    willr = ta_willr(high, low, close, willr_period)
    atr = ta_atr(high, low, close, atr_period)

    # Entry: price above SMA200 and oversold
    entry_condition = (close > sma200) & (willr < -80)

    signals = pd.Series(0, index=df.index)
    in_position = False
    entry_price = None
    stop_price = None

    # Vectorized approach: we'll mark entries and then exit on conditions
    # Simple implementation: track state in loop (for clarity)
    for i in range(len(df)):
        if not in_position and entry_condition.iloc[i]:
            signals.iloc[i] = 1
            in_position = True
            entry_price = close.iloc[i]
            stop_price = entry_price - stop_mult * atr.iloc[i]
        elif in_position:
            # Check exit: price hits stop or Williams recovers above -50 & close < swing low
            current_close = close.iloc[i]
            current_willr = willr.iloc[i]
            if current_close <= stop_price:
                signals.iloc[i] = 0
                in_position = False
            elif current_willr > -50:
                # Emergency exit if also close < recent swing low (simplified)
                signals.iloc[i] = 0
                in_position = False

    # Forward fill position
    signals = signals.replace(0, method='ffill').fillna(0)

    return signals