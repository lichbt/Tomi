"""Multi-Timeframe Trend + Entry Strategy."""
import pandas as pd
import numpy as np


def strategy_multi_timeframe(df: pd.DataFrame, params: dict) -> pd.Series:
    """Trend filter on higher TF simulation + RSI pullback + MACD momentum entry."""
    trend_sma_fast = params.get('trend_sma_fast', 50)
    trend_sma_slow = params.get('trend_sma_slow', 200)
    rsi_period = params.get('rsi_period', 14)
    rsi_low = params.get('rsi_low', 40)
    rsi_high = params.get('rsi_high', 60)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 2.0)

    close = df['close']
    high = df['high']
    low = df['low']

    # Trend MAs (simulating daily on H4 by using larger periods)
    sma_fast = close.rolling(trend_sma_fast).mean()
    sma_slow = close.rolling(trend_sma_slow).mean()
    trend_up = sma_fast > sma_slow
    trend_down = sma_fast < sma_slow

    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(rsi_period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(rsi_period).mean()
    rs = gain / (loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))

    # MACD histogram
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd_hist = (ema12 - ema26) - (ema12 - ema26).ewm(span=9).mean()

    # ATR
    tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    signals = pd.Series(0.0, index=df.index)
    position = 0
    peak = 0.0
    trough = 0.0

    for i in range(trend_sma_slow, len(df)):
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

        # Entry: trend + RSI pullback + MACD momentum
        if position == 0:
            if trend_up.iloc[i] and rsi.iloc[i] < rsi_low and macd_hist.iloc[i] > macd_hist.iloc[i-1]:
                position = 1
                peak = high.iloc[i]
            elif trend_down.iloc[i] and rsi.iloc[i] > rsi_high and macd_hist.iloc[i] < macd_hist.iloc[i-1]:
                position = -1
                trough = low.iloc[i]

        signals.iloc[i] = position

    return signals.astype(int)
