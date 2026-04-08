"""Keltner Channel Breakout Strategy.

Uses ATR-based envelope (Keltner Channels) for trend-following breakouts.
Price breaking above upper band in uptrend = long. Below lower band in
downtrend = short. EMA filter confirms trend direction.

Signal convention: +1 = long, -1 = short, 0 = flat.
"""
import pandas as pd
import numpy as np


def strategy_keltner_channels(df: pd.DataFrame, params: dict) -> pd.Series:
    """Keltner Channel breakout strategy.

    Upper Channel = EMA(mid, kc_period) + kc_multiplier * ATR(atr_period)
    Lower Channel = EMA(mid, kc_period) - kc_multiplier * ATR(atr_period)

    Entry:
    - Long: close crosses above upper band + EMA trend filter is up
    - Short: close crosses below lower band + EMA trend filter is down

    Exit: ATR trailing stop or signal reversal.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ['open', 'high', 'low', 'close'].
    params : dict
        ema_period     : int   - EMA period for centre line (default 20)
        atr_period     : int   - ATR period for channel width (default 10)
        kc_multiplier  : float - ATR multiplier for bands (default 1.5)
        trend_ema      : int   - long-term EMA trend filter (default 50)
        stop_mult      : float - trailing stop ATR multiplier (default 2.0)

    Returns
    -------
    pd.Series[int]
        Signal series shifted by 1 to prevent look-ahead bias.
    """
    ema_period = params.get('ema_period', 20)
    atr_period = params.get('atr_period', 10)
    kc_multiplier = params.get('kc_multiplier', 1.5)
    trend_ema_period = params.get('trend_ema', 50)
    stop_mult = params.get('stop_mult', 2.0)

    high = df['high'].astype(np.float64)
    low = df['low'].astype(np.float64)
    close = df['close'].astype(np.float64)
    typical = (high + low + close) / 3.0

    # Centre EMA (on typical price)
    centre = typical.ewm(span=ema_period, adjust=False).mean()

    # ATR
    prev_close = close.shift(1)
    tr = pd.concat([high - low, abs(high - prev_close), abs(low - prev_close)], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    # Keltner Channels
    upper = centre + kc_multiplier * atr
    lower = centre - kc_multiplier * atr

    # Trend filter (longer EMA)
    trend_ema = close.ewm(span=trend_ema_period, adjust=False).mean()
    trend_up = close > trend_ema
    trend_down = close < trend_ema

    signals = pd.Series(0, index=df.index, dtype=int)
    position = 0
    peak = 0.0
    trough = 0.0

    start_idx = max(trend_ema_period, ema_period, atr_period) + 1

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

        if position == 0:
            # Long breakout + trend filter
            if close.iloc[i] > upper.iloc[i] and close.iloc[i - 1] <= upper.iloc[i - 1] and trend_up.iloc[i]:
                position = 1
                peak = high.iloc[i]
            # Short breakdown + trend filter
            elif close.iloc[i] < lower.iloc[i] and close.iloc[i - 1] >= lower.iloc[i - 1] and trend_down.iloc[i]:
                position = -1
                trough = low.iloc[i]

        signals.iloc[i] = position

    return signals.shift(1).fillna(0).astype(int)
