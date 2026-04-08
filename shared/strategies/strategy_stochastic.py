"""Stochastic Oscillator Strategy.

Uses Stochastic %K and %D crossover with OB/OS zones and ATR trailing stops.
Trend filter via 200 SMA for directional bias.

Signal convention: +1 = long, -1 = short, 0 = flat.
"""
import pandas as pd
import numpy as np


def strategy_stochastic(df: pd.DataFrame, params: dict) -> pd.Series:
    """Stochastic Oscillator mean-reversion / momentum strategy.

    Entry signals:
    - Long: %K crosses above %D in oversold zone (< os_level) + uptrend
    - Short: %K crosses below %D in overbought zone (> ob_level) + downtrend

    Exits on ATR trailing stop or signal reversal.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ['open', 'high', 'low', 'close'].
    params : dict
        k_period   : int   - %K lookback window (default 14)
        k_smooth   : int   - %K smoothing (default 3)
        d_period   : int   - %D smoothing of %K (default 3)
        os_level   : float - oversold threshold (default 20)
        ob_level   : float - overbought threshold (default 80)
        sma_period : int   - trend filter SMA (default 200)
        atr_period : int   - ATR window for stops (default 14)
        stop_mult  : float - ATR multiplier for trailing stop (default 2.0)

    Returns
    -------
    pd.Series[int]
        Signal series shifted by 1 to prevent look-ahead bias.
    """
    k_period = params.get('k_period', 14)
    k_smooth = params.get('k_smooth', 3)
    d_period = params.get('d_period', 3)
    os_level = params.get('os_level', 20)
    ob_level = params.get('ob_level', 80)
    sma_period = params.get('sma_period', 200)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_mult', 2.0)

    high = df['high'].astype(np.float64)
    low = df['low'].astype(np.float64)
    close = df['close'].astype(np.float64)
    prev_close = close.shift(1)

    # Stochastic %K (raw)
    lowest_low = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    k_raw = 100.0 * (close - lowest_low) / (highest_high - lowest_low + 1e-9)

    # Smoothed %K and %D
    k = k_raw.rolling(k_smooth).mean()
    d = k.rolling(d_period).mean()

    # Trend filter
    sma = close.rolling(sma_period).mean()
    trend_up = close > sma
    trend_down = close < sma

    # ATR for stops
    tr = pd.concat([high - low, abs(high - prev_close), abs(low - prev_close)], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    signals = pd.Series(0, index=df.index, dtype=int)
    position = 0
    peak = 0.0
    trough = 0.0

    start_idx = max(sma_period, atr_period, k_period + k_smooth + d_period)

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
            k_val = k.iloc[i]
            d_val = d.iloc[i]
            k_prev = k.iloc[i - 1]
            d_prev = d.iloc[i - 1]

            # Long: %K crosses above %D in oversold + uptrend
            if k_prev < d_prev and k_val > d_val and k_val < os_level and trend_up.iloc[i]:
                position = 1
                peak = high.iloc[i]
            # Short: %K crosses below %D in overbought + downtrend
            elif k_prev > d_prev and k_val < d_val and k_val > ob_level and trend_down.iloc[i]:
                position = -1
                trough = low.iloc[i]

        signals.iloc[i] = position

    return signals.shift(1).fillna(0).astype(int)
