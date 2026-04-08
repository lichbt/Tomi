"""Volatility Expansion with Volume Confirmation."""
import pandas as pd
import numpy as np


def strategy_volatility_volume(df: pd.DataFrame, params: dict) -> pd.Series:
    """BB squeeze breakout + volume filter + trend filter + ATR stop."""
    bb_period = params.get('bb_period', 20)
    bb_std = params.get('bb_std', 2.0)
    squeeze_lookback = params.get('squeeze_lookback', 100)
    squeeze_pct = params.get('squeeze_percentile', 10)
    sma_filter = params.get('sma_filter', 200)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 2.0)
    vol_period = params.get('vol_period', 20)
    vol_mult = params.get('vol_mult', 1.5)

    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']

    # Bollinger Bands
    ma = close.rolling(bb_period).mean()
    std = close.rolling(bb_period).std()
    upper = ma + bb_std * std
    lower = ma - bb_std * std

    # BB Width
    bb_width = (upper - lower) / (ma + 1e-9)
    bb_width_pct = bb_width.rolling(squeeze_lookback).rank(pct=True) * 100

    # SMA trend filter
    sma200 = close.rolling(sma_filter).mean()

    # Volume filter
    vol_ma = volume.rolling(vol_period).mean()
    vol_ok = volume > vol_ma * vol_mult

    # ATR
    tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    signals = pd.Series(0.0, index=df.index)
    position = 0
    peak = 0.0
    trough = 0.0

    for i in range(squeeze_lookback, len(df)):
        if pd.isna(atr.iloc[i]) or atr.iloc[i] <= 0:
            signals.iloc[i] = position
            continue

        # Exit
        if position == 1:
            peak = max(peak, high.iloc[i])
            if low.iloc[i] <= peak - stop_mult * atr.iloc[i]:
                position = 0
        elif position == -1:
            trough = min(trough, low.iloc[i])
            if high.iloc[i] >= trough + stop_mult * atr.iloc[i]:
                position = 0

        # Entry with volume confirmation
        was_squeeze = bb_width_pct.iloc[i-1] < squeeze_pct if i > 0 else False
        if position == 0 and was_squeeze and vol_ok.iloc[i]:
            if close.iloc[i] > upper.iloc[i] and close.iloc[i] > sma200.iloc[i]:
                position = 1
                peak = high.iloc[i]
            elif close.iloc[i] < lower.iloc[i] and close.iloc[i] < sma200.iloc[i]:
                position = -1
                trough = low.iloc[i]

        signals.iloc[i] = position

    return signals.astype(int)
