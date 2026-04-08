# Strategy: VWAP Pullback Mean Reversion
# Author: Strategy Coder Agent
# Edge: Volume-weighted mean reversion with volume exhaustion confirmation
# Libraries: pandas, numpy only

import pandas as pd
import numpy as np
from typing import Dict


def strategy_vwap_pullback(
    df: pd.DataFrame,
    params: Dict[str, any]
) -> pd.Series:
    """
    VWAP Pullback Mean Reversion.

    Logic:
      1. Compute rolling VWAP from OHLCV (anchored over lookback period)
      2. Compute VWAP deviation bands (1, 2, 3 SD above/below)
      3. Long: price drops to -2SD band, volume spike, then closes back inside
      4. Short: price rises to +2SD band, volume spike, then closes back inside
      5. Exit: price reaches VWAP (mean), or ATR trailing stop

    Args:
        df: OHLCV DataFrame
        params: {
            'vwap_period': int (default 50),        # VWAP anchor window
            'entry_band': float (default 2.0),      # SD band for entry
            'exit_band': float (default 0.5),       # SD band for exit
            'vol_mult': float (default 2.0),        # Volume spike multiplier
            'vol_period': int (default 20),         # Volume average lookback
            'atr_period': int (default 14),
            'stop_atr_mult': float (default 2.5),
        }

    Returns:
        pd.Series of signals: +1 (long), -1 (short), 0 (flat)
    """
    required = {'open', 'high', 'low', 'close', 'volume'}
    if not required.issubset(df.columns):
        raise ValueError(f'Missing columns: {required - set(df.columns)}')

    vwap_period = params.get('vwap_period', 50)
    entry_band = params.get('entry_band', 2.0)
    exit_band = params.get('exit_band', 0.5)
    vol_mult = params.get('vol_mult', 2.0)
    vol_period = params.get('vol_period', 20)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 2.5)

    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']

    # Rolling VWAP (approximation for multi-day H4: use typical price × volume)
    typical_price = (high + low + close) / 3
    tp_cum = typical_price.rolling(vwap_period).sum()
    vol_cum = volume.rolling(vwap_period).sum()
    vwap = tp_cum / (vol_cum + 1e-9)

    # VWAP deviation
    vwap_dev = typical_price - vwap
    vwap_std = vwap_dev.rolling(vwap_period).std(ddof=0)

    upper_entry = vwap + entry_band * vwap_std
    lower_entry = vwap - entry_band * vwap_std
    upper_exit = vwap + exit_band * vwap_std
    lower_exit = vwap - exit_band * vwap_std

    # Volume spike confirmation
    vol_avg = volume.rolling(vol_period).mean()
    vol_spike = volume > (vol_avg * vol_mult)

    # ATR for trailing stop
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    # Entry: price wicks beyond band, volume spike, closes back inside
    # Long: low below lower_entry, volume spike, close above lower_entry
    long_entry = (
        (low.shift(1) < lower_entry.shift(1)) &
        vol_spike.shift(1) &
        (close > lower_entry)
    )

    # Short: high above upper_entry, volume spike, close below upper_entry
    short_entry = (
        (high.shift(1) > upper_entry.shift(1)) &
        vol_spike.shift(1) &
        (close < upper_entry)
    )

    # Generate signals
    signals = pd.Series(0, index=df.index)
    signals[long_entry] = 1
    signals[short_entry] = -1

    # Exit: price crosses back toward VWAP
    exit_long = close > vwap
    exit_short = close < vwap

    # ATR trailing stop
    ts_long = close - atr * stop_mult
    ts_short = close + atr * stop_mult
    stop_long = close.shift(1) < ts_long.shift(1)
    stop_short = close.shift(1) > ts_short.shift(1)

    signals[exit_long | stop_long] = 0
    signals[exit_short | stop_short] = 0

    # Flip
    signals[(signals == 1) & signals.shift(1).eq(-1)] = 0
    signals[(signals == -1) & signals.shift(1).eq(1)] = 0

    signals = signals.shift(1).fillna(0).astype(int)

    assert len(signals) == len(df)
    return signals
