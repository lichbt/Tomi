# Strategy: Smart Money Concepts — Order Blocks + Fair Value Gaps
# Author: Strategy Coder Agent
# Edge: Detects institutional footprints — OBs, FVGs, liquidity sweeps
# Libraries: pandas, numpy only

import pandas as pd
import numpy as np
from typing import Dict


def detect_order_blocks(df: pd.DataFrame, lookback: int = 5) -> pd.DataFrame:
    """Detect bullish and bearish order blocks."""
    df = df.copy()

    # Impulse candle: body size > 2× average body
    df['body'] = abs(df['close'] - df['open'])
    df['body_avg'] = df['body'].rolling(lookback).mean()
    df['impulse_bull'] = (df['close'] > df['open']) & (df['body'] > 2 * df['body_avg'])
    df['impulse_bear'] = (df['close'] < df['open']) & (df['body'] > 2 * df['body_avg'])

    # Bullish OB: last bearish candle before bullish impulse
    df['bullish_ob'] = (
        (df['close'].shift(1) < df['open'].shift(1)) &
        df['impulse_bull']
    )

    # Bearish OB: last bullish candle before bearish impulse
    df['bearish_ob'] = (
        (df['close'].shift(1) > df['open'].shift(1)) &
        df['impulse_bear']
    )

    # Store OB zones
    df['ob_high'] = np.where(df['bullish_ob'], df['high'].shift(1), np.nan)
    df['ob_low'] = np.where(df['bullish_ob'], df['low'].shift(1), np.nan)
    df['ob_high_bear'] = np.where(df['bearish_ob'], df['high'].shift(1), np.nan)
    df['ob_low_bear'] = np.where(df['bearish_ob'], df['low'].shift(1), np.nan)

    # Forward-fill OB zones (keep last detected OB until new one)
    df['bull_ob_h'] = df['ob_high'].ffill()
    df['bull_ob_l'] = df['ob_low'].ffill()
    df['bear_ob_h'] = df['ob_high_bear'].ffill()
    df['bear_ob_l'] = df['ob_low_bear'].ffill()

    return df


def detect_fvg(df: pd.DataFrame) -> pd.DataFrame:
    """Detect Fair Value Gaps (3-candle imbalance)."""
    df = df.copy()

    # Bullish FVG: low[0] > high[-2] (gap up)
    df['fvg_bull'] = df['low'] > df['high'].shift(2)
    df['fvg_bull_high'] = np.where(df['fvg_bull'], df['high'].shift(1), np.nan)
    df['fvg_bull_low'] = np.where(df['fvg_bull'], df['low'].shift(2), np.nan)

    # Bearish FVG: high[0] < low[-2] (gap down)
    df['fvg_bear'] = df['high'] < df['low'].shift(2)
    df['fvg_bear_high'] = np.where(df['fvg_bear'], df['high'].shift(2), np.nan)
    df['fvg_bear_low'] = np.where(df['fvg_bear'], df['low'].shift(1), np.nan)

    # Forward fill
    df['fvg_bull_h'] = df['fvg_bull_high'].ffill()
    df['fvg_bull_l'] = df['fvg_bull_low'].ffill()
    df['fvg_bear_h'] = df['fvg_bear_high'].ffill()
    df['fvg_bear_l'] = df['fvg_bear_low'].ffill()

    return df


def detect_liquidity_sweep(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Detect sweep of recent swing high/low with reversal."""
    df = df.copy()

    swing_low = df['low'].rolling(period).min().shift(1)
    swing_high = df['high'].rolling(period).max().shift(1)

    # Sweep low: wick below swing_low then close back above
    df['sweep_low'] = (df['low'] < swing_low) & (df['close'] > df['open'])

    # Sweep high: wick above swing_high then close back below
    df['sweep_high'] = (df['high'] > swing_high) & (df['close'] < df['open'])

    return df


def strategy_smc_order_blocks(
    df: pd.DataFrame,
    params: Dict[str, any]
) -> pd.Series:
    """
    Smart Money Concepts strategy.

    Entry Long:  sweep_low AND price retraces into bullish OB or FVG
    Entry Short: sweep_high AND price retraces into bearish OB or FVG
    Exit:        Opposite signal or ATR trailing stop

    Args:
        df: OHLCV DataFrame
        params: {
            'ob_lookback': int (default 5),
            'atr_period': int (default 14),
            'stop_atr_mult': float (default 2.5),
            'sweep_period': int (default 20),
        }

    Returns:
        pd.Series of signals: +1 (long), -1 (short), 0 (flat)
    """
    required = {'open', 'high', 'low', 'close', 'volume'}
    if not required.issubset(df.columns):
        raise ValueError(f'Missing columns: {required - set(df.columns)}')

    ob_lookback = params.get('ob_lookback', 5)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 2.5)
    sweep_period = params.get('sweep_period', 20)

    df = df.copy()

    # ATR for trailing stop
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift(1)).abs(),
        (df['low'] - df['close'].shift(1)).abs()
    ], axis=1).max(axis=1)
    df['atr'] = tr.rolling(atr_period).mean()

    # Detect SMC components
    df = detect_order_blocks(df, ob_lookback)
    df = detect_fvg(df)
    df = detect_liquidity_sweep(df, sweep_period)

    # Price in bullish OB
    df['in_bull_ob'] = (df['bull_ob_l'].notna()) & (df['low'] <= df['bull_ob_h']) & (df['high'] >= df['bull_ob_l'])

    # Price in bearish OB
    df['in_bear_ob'] = (df['bear_ob_l'].notna()) & (df['low'] <= df['bear_ob_h']) & (df['high'] >= df['bear_ob_l'])

    # Price in bullish FVG
    df['in_bull_fvg'] = (df['fvg_bull_l'].notna()) & (df['low'] <= df['fvg_bull_h']) & (df['high'] >= df['fvg_bull_l'])

    # Price in bearish FVG
    df['in_bear_fvg'] = (df['fvg_bear_l'].notna()) & (df['low'] <= df['fvg_bear_h']) & (df['high'] >= df['fvg_bear_l'])

    # Entry conditions
    df['long_entry'] = (
        df['sweep_low'].shift(1) &
        (df['in_bull_ob'] | df['in_bull_fvg'])
    )

    df['short_entry'] = (
        df['sweep_high'].shift(1) &
        (df['in_bear_ob'] | df['in_bear_fvg'])
    )

    # Generate signals
    signals = pd.Series(0, index=df.index)
    signals[df['long_entry']] = 1
    signals[df['short_entry']] = -1

    # Flip detection: exit on opposite signal
    flip_long = signals.eq(1) & signals.shift(1).eq(-1)
    flip_short = signals.eq(-1) & signals.shift(1).eq(1)

    # ATR trailing stop exit
    atr = df['atr']
    trailing_stop_long = df['close'].rolling(20).min() - atr * stop_mult
    trailing_stop_short = df['close'].rolling(20).max() + atr * stop_mult

    stop_long = df['close'].shift(1) < trailing_stop_long.shift(1)
    stop_short = df['close'].shift(1) > trailing_stop_short.shift(1)

    signals[flip_long | stop_long] = 0
    signals[flip_short | stop_short] = 0

    # Shift to prevent look-ahead bias
    signals = signals.shift(1)

    # Handle NaNs
    signals = signals.fillna(0).astype(int)

    # Validate
    assert len(signals) == len(df), f'Signal length mismatch: {len(signals)} vs {len(df)}'
    assert set(signals.unique()).issubset({-1, 0, 1}), f'Invalid signal values: {signals.unique()}'

    return signals
