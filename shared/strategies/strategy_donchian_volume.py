"""Donchian Breakout with Volume Confirmation."""
import pandas as pd
import numpy as np


def strategy_donchian_volume(df: pd.DataFrame, params: dict) -> pd.Series:
    """Donchian breakout + volume filter + trend filter + ATR stop."""
    donch_window = params.get('donch_period', 20)
    sma_filter = params.get('sma_filter', 200)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 2.0)
    vol_period = params.get('vol_period', 20)
    vol_mult = params.get('vol_mult', 1.5)

    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']

    # Donchian channels
    donch_high = high.rolling(donch_window).max()
    donch_low = low.rolling(donch_window).min()

    # SMA trend filter
    sma = close.rolling(sma_filter).mean()

    # Volume filter
    vol_ma = volume.rolling(vol_period).mean()
    vol_ok = volume > vol_ma * vol_mult

    # ATR
    tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    # Previous channel values
    prev_high = donch_high.shift(1)
    prev_low = donch_low.shift(1)

    # Breakout conditions WITH volume confirmation
    long_break = (close > prev_high) & (close > sma) & vol_ok
    short_break = (close < prev_low) & (close < sma) & vol_ok

    signals = pd.Series(0.0, index=df.index)
    position = 0
    peak = 0.0
    trough = 0.0

    for i in range(sma_filter, len(df)):
        current_close = close.iloc[i]
        current_high = high.iloc[i]
        current_low = low.iloc[i]
        current_atr = atr.iloc[i]

        if pd.isna(current_atr) or current_atr <= 0:
            signals.iloc[i] = position
            continue

        # Exit
        if position == 1:
            peak = max(peak, current_high)
            if current_low <= peak - stop_mult * current_atr:
                position = 0
        elif position == -1:
            trough = min(trough, current_low)
            if current_high >= trough + stop_mult * current_atr:
                position = 0

        # Entry
        if position == 0:
            if long_break.iloc[i]:
                position = 1
                peak = current_high
            elif short_break.iloc[i]:
                position = -1
                trough = current_low

        signals.iloc[i] = position

    return signals.astype(int)
