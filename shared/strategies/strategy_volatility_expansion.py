"""Volatility Expansion Breakout Strategy."""
import pandas as pd
import numpy as np


def strategy_volatility_expansion(df: pd.DataFrame, params: dict) -> pd.Series:
    """Squeeze detection + breakout entry with trend filter."""
    bb_period = params.get('bb_period', 20)
    bb_std = params.get('bb_std', 2.0)
    squeeze_lookback = params.get('squeeze_lookback', 100)
    squeeze_pct = params.get('squeeze_percentile', 10)
    sma_filter = params.get('sma_filter', 200)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 2.0)
    risk_model = params.get('risk_model', 'baseline')
    if risk_model == 'breakeven':
        breakeven_atr = params.get('breakeven_atr', 2.0)
        breakeven_buffer = params.get('breakeven_buffer', 0.5)
    elif risk_model == 'percent_trail':
        profit_switch_atr = params.get('profit_switch_atr', 4.0)
        percent_trail = params.get('percent_trail', 0.02)

    close = df['close']
    high = df['high']
    low = df['low']

    # Bollinger Bands
    ma = close.rolling(bb_period).mean()
    std = close.rolling(bb_period).std()
    upper = ma + bb_std * std
    lower = ma - bb_std * std

    # BB Width (normalized)
    bb_width = (upper - lower) / (ma + 1e-9)
    bb_width_pct = bb_width.rolling(squeeze_lookback).rank(pct=True) * 100

    # SMA trend filter
    sma200 = close.rolling(sma_filter).mean()

    # ATR
    tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    signals = pd.Series(0.0, index=df.index)
    position = 0
    peak = 0.0
    trough = 0.0
    entry_price = 0.0

    for i in range(squeeze_lookback, len(df)):
        if pd.isna(atr.iloc[i]) or atr.iloc[i] <= 0:
            signals.iloc[i] = position
            continue

        # Exit
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

        # Entry: breakout after squeeze
        was_squeeze = bb_width_pct.iloc[i-1] < squeeze_pct if i > 0 else False
        if position == 0 and was_squeeze:
            if close.iloc[i] > upper.iloc[i] and close.iloc[i] > sma200.iloc[i]:
                position = 1
                entry_price = close.iloc[i]
                peak = high.iloc[i]
            elif close.iloc[i] < lower.iloc[i] and close.iloc[i] < sma200.iloc[i]:
                position = -1
                entry_price = close.iloc[i]
                trough = low.iloc[i]

        signals.iloc[i] = position

    return signals.astype(int)
