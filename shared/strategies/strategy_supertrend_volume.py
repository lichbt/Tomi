"""Supertrend + Volume Confirmation Strategy.

Supertrend flip confirmed by volume spike > 1.5x volume MA(20).
"""
import pandas as pd
import numpy as np


def _supertrend(high, low, close, period, multiplier):
    atr = _atr(high, low, close, period)
    hl2 = (high + low) / 2.0
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr
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


def strategy_supertrend_volume(df: pd.DataFrame, params: dict) -> pd.Series:
    st_period = params.get('st_period', 10)
    st_mult = params.get('st_multiplier', 3.0)
    vol_period = params.get('vol_period', 20)
    vol_mult = params.get('vol_multiplier', 1.5)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 2.5)
    risk_model = params.get('risk_model', 'baseline')
    if risk_model == 'breakeven':
        breakeven_atr = params.get('breakeven_atr', 2.0)
        breakeven_buffer = params.get('breakeven_buffer', 0.5)
    elif risk_model == 'percent_trail':
        profit_switch_atr = params.get('profit_switch_atr', 4.0)
        percent_trail = params.get('percent_trail', 0.02)

    close = df['close'].astype(np.float64)
    high = df['high'].astype(np.float64)
    low = df['low'].astype(np.float64)
    volume = df['volume'].astype(np.float64)

    trend, _ = _supertrend(high, low, close, st_period, st_mult)
    vol_ma = volume.rolling(vol_period).mean()
    vol_spike = volume > (vol_ma * vol_mult)
    atr = _atr(high, low, close, atr_period)

    signals = pd.Series(0, index=df.index, dtype=int)
    position = 0
    peak = 0.0
    trough = 0.0
    entry_price = 0.0

    start = max(st_period, vol_period, atr_period)
    for i in range(start, len(df)):
        if np.isnan(atr.iloc[i]) or atr.iloc[i] <= 0:
            signals.iloc[i] = position
            continue

        if position == 1:
            peak = max(peak, high.iloc[i])
            trail_stop = peak - stop_mult * atr.iloc[i]
            if risk_model == 'breakeven':
                profit = close.iloc[i] - entry_price
                if profit >= breakeven_atr * atr.iloc[i]:
                    trail_stop = max(trail_stop, entry_price + breakeven_buffer * atr.iloc[i])
            elif risk_model == 'percent_trail':
                profit = close.iloc[i] - entry_price
                if profit >= profit_switch_atr * atr.iloc[i]:
                    trail_stop = peak * (1 - percent_trail)
            if low.iloc[i] <= trail_stop:
                position = 0
        elif position == -1:
            trough = min(trough, low.iloc[i])
            trail_stop = trough + stop_mult * atr.iloc[i]
            if risk_model == 'breakeven':
                profit = entry_price - close.iloc[i]
                if profit >= breakeven_atr * atr.iloc[i]:
                    trail_stop = min(trail_stop, entry_price - breakeven_buffer * atr.iloc[i])
            elif risk_model == 'percent_trail':
                profit = entry_price - close.iloc[i]
                if profit >= profit_switch_atr * atr.iloc[i]:
                    trail_stop = trough * (1 + percent_trail)
            if high.iloc[i] >= trail_stop:
                position = 0

        if position == 0:
            t_now, t_prev = trend.iloc[i], trend.iloc[i - 1]
            vs = vol_spike.iloc[i]
            if t_now == 1 and t_prev == -1 and vs:
                position = 1
                entry_price = close.iloc[i]
                peak = high.iloc[i]
            elif t_now == -1 and t_prev == 1 and vs:
                position = -1
                entry_price = close.iloc[i]
                trough = low.iloc[i]

        signals.iloc[i] = position

    return signals.shift(1).fillna(0).astype(int)
