"""Supertrend + EMA Trend Filter Strategy.

Supertrend (ATR-based trailing stop line) combined with 200 EMA for trend filter.
Entry long: Supertrend flips bullish AND price > EMA(200).
Exit: Supertrend flips bearish.
"""
import pandas as pd
import numpy as np


def _supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
                period: int, multiplier: float) -> pd.Series:
    """Calculate Supertrend indicator. Returns +1 (bullish) or -1 (bearish)."""
    atr = _atr(high, low, close, period)
    hl2 = (high + low) / 2.0
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr

    trend = pd.Series(1, index=close.index, dtype=int)
    st_line = pd.Series(0.0, index=close.index)

    for i in range(period, len(close)):
        if i == period:
            st_line.iloc[i] = upper.iloc[i]
            trend.iloc[i] = 1
            continue

        if close.iloc[i - 1] <= st_line.iloc[i - 1]:
            st_line.iloc[i] = min(upper.iloc[i], st_line.iloc[i - 1])
            if close.iloc[i] > st_line.iloc[i]:
                trend.iloc[i] = 1
            else:
                trend.iloc[i] = -1
        else:
            st_line.iloc[i] = max(lower.iloc[i], st_line.iloc[i - 1])
            if close.iloc[i] < st_line.iloc[i]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = 1

    return trend, st_line


def _atr(high, low, close, period):
    prev_close = close.shift(1)
    tr = pd.concat([high - low, abs(high - prev_close), abs(low - prev_close)], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def strategy_supertrend_ema(df: pd.DataFrame, params: dict) -> pd.Series:
    """Supertrend + EMA 200 trend filter.

    Parameters
    ----------
    df : pd.DataFrame with ['open', 'high', 'low', 'close', 'volume']
    params : dict with st_period, st_multiplier, ema_period, atr_period, stop_atr_mult
    """
    st_period = params.get('st_period', 10)
    st_mult = params.get('st_multiplier', 3.0)
    ema_period = params.get('ema_period', 200)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 2.5)

    close = df['close'].astype(np.float64)
    high = df['high'].astype(np.float64)
    low = df['low'].astype(np.float64)
    prev_close = close.shift(1)

    trend, _ = _supertrend(high, low, close, st_period, st_mult)
    ema = close.ewm(span=ema_period, adjust=False).mean()
    atr = _atr(high, low, close, atr_period)

    signals = pd.Series(0, index=df.index, dtype=int)
    position = 0
    peak = 0.0
    trough = 0.0

    start = max(st_period, ema_period, atr_period)
    for i in range(start, len(df)):
        if np.isnan(atr.iloc[i]) or atr.iloc[i] <= 0:
            signals.iloc[i] = position
            continue

        # Trailing stop
        if position == 1:
            peak = max(peak, high.iloc[i])
            if low.iloc[i] <= peak - stop_mult * atr.iloc[i]:
                position = 0
        elif position == -1:
            trough = min(trough, low.iloc[i])
            if high.iloc[i] >= trough + stop_mult * atr.iloc[i]:
                position = 0

        # Entry
        if position == 0:
            t_now = trend.iloc[i]
            t_prev = trend.iloc[i - 1]
            if t_now == 1 and t_prev == -1 and close.iloc[i] > ema.iloc[i]:
                position = 1
                peak = high.iloc[i]
            elif t_now == -1 and t_prev == 1 and close.iloc[i] < ema.iloc[i]:
                position = -1
                trough = low.iloc[i]

        signals.iloc[i] = position

    return signals.shift(1).fillna(0).astype(int)
