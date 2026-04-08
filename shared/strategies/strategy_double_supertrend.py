"""Double Supertrend — Fast + Slow confluence strategy.

Fast Supertrend (7, 2.0) + Slow Supertrend (14, 3.0).
Entry when BOTH flip bullish/bearish. Exit when Fast flips.
"""
import pandas as pd
import numpy as np


def _supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
                period: int, multiplier: float):
    atr_val = _atr(high, low, close, period)
    hl2 = (high + low) / 2.0
    upper = hl2 + multiplier * atr_val
    lower = hl2 - multiplier * atr_val
    trend = pd.Series(1, index=close.index, dtype=int)
    st_line = pd.Series(np.nan, index=close.index)
    for i in range(period, len(close)):
        if i == period:
            st_line.iloc[i] = upper.iloc[i]
            trend.iloc[i] = 1
            continue
        if close.iloc[i - 1] <= st_line.iloc[i - 1]:
            st_line.iloc[i] = min(upper.iloc[i], st_line.iloc[i - 1])
            trend.iloc[i] = 1 if close.iloc[i] > st_line.iloc[i] else -1
        else:
            st_line.iloc[i] = max(lower.iloc[i], st_line.iloc[i - 1])
            trend.iloc[i] = -1 if close.iloc[i] < st_line.iloc[i] else 1
    return trend, st_line


def _atr(high, low, close, period):
    prev_close = close.shift(1)
    tr = pd.concat([high - low, abs(high - prev_close), abs(low - prev_close)], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def strategy_double_supertrend(df: pd.DataFrame, params: dict) -> pd.Series:
    fast_p = params.get('fast_period', 7)
    fast_m = params.get('fast_multiplier', 2.0)
    slow_p = params.get('slow_period', 14)
    slow_m = params.get('slow_multiplier', 3.0)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 2.5)

    close = df['close'].astype(np.float64)
    high = df['high'].astype(np.float64)
    low = df['low'].astype(np.float64)

    trend_f, _ = _supertrend(high, low, close, fast_p, fast_m)
    trend_s, _ = _supertrend(high, low, close, slow_p, slow_m)
    atr = _atr(high, low, close, atr_period)

    signals = pd.Series(0, index=df.index, dtype=int)
    position = 0
    peak = 0.0
    trough = 0.0

    start = max(fast_p, slow_p, atr_period)
    for i in range(start, len(df)):
        if np.isnan(atr.iloc[i]) or atr.iloc[i] <= 0:
            signals.iloc[i] = position
            continue

        if position == 1:
            peak = max(peak, high.iloc[i])
            if low.iloc[i] <= peak - stop_mult * atr.iloc[i]:
                position = 0
        elif position == -1:
            trough = min(trough, low.iloc[i])
            if high.iloc[i] >= trough + stop_mult * atr.iloc[i]:
                position = 0

        if position == 0:
            f_now, f_prev = trend_f.iloc[i], trend_f.iloc[i - 1]
            s_now, s_prev = trend_s.iloc[i], trend_s.iloc[i - 1]
            # Both flip bullish
            if f_now == 1 and s_now == 1 and (f_prev == -1 or s_prev == -1):
                position = 1
                peak = high.iloc[i]
            elif f_now == -1 and s_now == -1 and (f_prev == 1 or s_prev == 1):
                position = -1
                trough = low.iloc[i]

        signals.iloc[i] = position

    return signals.shift(1).fillna(0).astype(int)
