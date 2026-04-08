"""RSI Mean Reversion with Bollinger Band Filter - Fixed."""
import pandas as pd
import numpy as np


def strategy_rsi_mean_reversion(df: pd.DataFrame, params: dict) -> pd.Series:
    """RSI + Bollinger Band mean reversion with discrete exits."""
    rsi_period = params.get('rsi_period', 14)
    bb_period = params.get('bb_period', 20)
    bb_std = params.get('bb_std', 2.0)
    sma_filter = params.get('sma_filter', 200)
    rsi_threshold = params.get('rsi_threshold', 30)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 2.0)

    close = df['close']
    high = df['high']
    low = df['low']

    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(rsi_period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(rsi_period).mean()
    rs = gain / (loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))

    # Bollinger Bands
    ma = close.rolling(bb_period).mean()
    std = close.rolling(bb_period).std()
    upper = ma + bb_std * std
    lower = ma - bb_std * std

    # SMA trend filter
    sma200 = close.rolling(sma_filter).mean()

    # ATR for stops
    tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    signals = pd.Series(0, index=df.index)
    position = 0
    entry_price = 0.0
    peak = 0.0
    trough = 0.0

    for i in range(sma_filter, len(df)):
        if pd.isna(rsi.iloc[i]) or pd.isna(atr.iloc[i]) or atr.iloc[i] <= 0:
            signals.iloc[i] = position
            continue

        # Exit logic
        if position == 1:  # Long
            peak = max(peak, high.iloc[i])
            # Exit on RSI recovery, stop hit, or opposite signal
            if rsi.iloc[i] > 50 or low.iloc[i] <= entry_price - stop_mult * atr.iloc[i]:
                position = 0
        elif position == -1:  # Short
            trough = min(trough, low.iloc[i])
            if rsi.iloc[i] < 50 or high.iloc[i] >= entry_price + stop_mult * atr.iloc[i]:
                position = 0

        # Entry logic
        if position == 0:
            if rsi.iloc[i] < rsi_threshold and close.iloc[i] <= lower.iloc[i] and close.iloc[i] > sma200.iloc[i]:
                position = 1
                entry_price = close.iloc[i]
                peak = high.iloc[i]
            elif rsi.iloc[i] > (100 - rsi_threshold) and close.iloc[i] >= upper.iloc[i] and close.iloc[i] < sma200.iloc[i]:
                position = -1
                entry_price = close.iloc[i]
                trough = low.iloc[i]

        signals.iloc[i] = position

    return signals.astype(int)
