# Strategy: Z-Score Rolling Mean Reversion
# Author: Strategy Coder Agent
# Edge: Pure statistical mean reversion — normalize returns, trade extremes
# Libraries: pandas, numpy only

import pandas as pd
import numpy as np
from typing import Dict


def strategy_zscore_mean_reversion(
    df: pd.DataFrame,
    params: Dict[str, any]
) -> pd.Series:
    """
    Z-Score Rolling Mean Reversion (position-holding mode).

    Logic:
      1. Calculate rolling z-score: (price - SMA) / rolling_std
      2. Long when z-score < -entry_z (oversold extreme)
      3. Short when z-score > +entry_z (overbought extreme)
      4. Exit when z-score crosses back toward 0 (exit_z threshold)
      5. ATR trailing stop for catastrophic loss protection

    Args:
        df: OHLCV DataFrame
        params: {
            'lookback': int (default 50),
            'entry_z': float (default 2.0),
            'exit_z': float (default 0.5),
            'ma_type': str (default 'sma'),
            'atr_period': int (default 14),
            'stop_atr_mult': float (default 3.0),
        }

    Returns:
        pd.Series of signals: +1 (long), -1 (short), 0 (flat)
    """
    required = {'open', 'high', 'low', 'close', 'volume'}
    if not required.issubset(df.columns):
        raise ValueError(f'Missing columns: {required - set(df.columns)}')

    lookback = params.get('lookback', 50)
    entry_z = params.get('entry_z', 2.0)
    exit_z = params.get('exit_z', 0.5)
    ma_type = params.get('ma_type', 'sma')
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 3.0)

    close = df['close']

    # Central tendency
    if ma_type == 'ema':
        ma = close.ewm(span=lookback, adjust=False).mean()
    else:
        ma = close.rolling(lookback).mean()

    # Rolling standard deviation
    rolling_std = close.rolling(lookback).std(ddof=0)

    # Z-score
    zscore = (close - ma) / (rolling_std + 1e-9)

    # ATR
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - close.shift(1)).abs(),
        (df['low'] - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    # Position-holding
    signals = pd.Series(0, index=df.index)
    position = 0
    peak = 0.0
    trough = 0.0

    start_i = max(lookback, atr_period) + 1
    for i in range(start_i, len(df)):
        zv = zscore.iloc[i]
        if np.isnan(zv) or np.isnan(atr.iloc[i]):
            continue

        if position == 1:
            peak = max(peak, df['high'].iloc[i])
            # Exit: z-score crosses back toward mean OR trailing stop
            if zv > -exit_z or df['low'].iloc[i] <= peak - atr.iloc[i] * stop_mult:
                position = 0
            elif zv > entry_z:  # Flip to short
                position = -1
                trough = df['low'].iloc[i]
        elif position == -1:
            trough = min(trough, df['low'].iloc[i])
            if zv < exit_z or df['high'].iloc[i] >= trough + atr.iloc[i] * stop_mult:
                position = 0
            elif zv < -entry_z:  # Flip to long
                position = 1
                peak = df['high'].iloc[i]
        else:
            if zv < -entry_z:
                position = 1
                peak = df['high'].iloc[i]
            elif zv > entry_z:
                position = -1
                trough = df['low'].iloc[i]

        signals.iloc[i] = position

    signals = signals.shift(1).fillna(0).astype(int)
    assert len(signals) == len(df)
    return signals
