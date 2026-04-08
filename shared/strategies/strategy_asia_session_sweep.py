# Strategy: Asia Session Sweep (TJR Model)
# Author: Strategy Coder Agent
# Edge: Session-range liquidity raid + market structure shift reversal
# Libraries: pandas, numpy only

import pandas as pd
import numpy as np
from typing import Dict


def strategy_asia_session_sweep(
    df: pd.DataFrame,
    params: Dict[str, any]
) -> pd.Series:
    """
    Asia Session Sweep strategy (TJR-inspired).

    Logic:
      1. Mark Asia session high/low (bars 00:00-08:00 UTC)
      2. Wait for liquidity raid: wick above Asia high or below Asia low
      3. Market Structure Shift: strong break of nearest swing
      4. Entry: retracement back into Asia range
      5. Exit: opposite Asia level or ATR trailing stop

    Works best on Forex pairs (H4 or intraday).

    Args:
        df: OHLCV DataFrame (expects timezone-aware or UTC index)
        params: {
            'swing_period': int (default 10),
            'atr_period': int (default 14),
            'stop_atr_mult': float (default 2.5),
            'min_sweep_pct': float (default 0.001),
        }

    Returns:
        pd.Series of signals: +1 (long), -1 (short), 0 (flat)
    """
    required = {'open', 'high', 'low', 'close', 'volume'}
    if not required.issubset(df.columns):
        raise ValueError(f'Missing columns: {required - set(df.columns)}')

    swing_period = params.get('swing_period', 10)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 2.5)
    min_sweep_pct = params.get('min_sweep_pct', 0.001)

    df = df.copy()

    # Determine UTC hour from index
    if df.index.tzinfo is not None:
        hours = df.index.tz_convert('UTC').hour
    else:
        # Assume UTC if no timezone
        hours = df.index.hour if hasattr(df.index, 'hour') else pd.DatetimeIndex(df.index).hour

    # Asia session hours: 00:00 - 08:00 UTC (inclusive on H4 this captures ~2 bars)
    is_asia = hours.isin(range(0, 9))  # 0-8

    # Rolling Asia high/low: forward-fill the max/min of Asia bars
    df['is_asia'] = is_asia
    df['asia_high'] = np.where(df['is_asia'], df['high'], np.nan)
    df['asia_low'] = np.where(df['is_asia'], df['low'], np.nan)

    # Forward-fill Asia levels (they persist until next Asia session updates them)
    # Use a simple approach: at each bar, the last seen session's high/low
    df['asia_h'] = df['asia_high'].ffill()
    df['asia_l'] = df['asia_low'].ffill()

    # ATR
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift(1)).abs(),
        (df['low'] - df['close'].shift(1)).abs()
    ], axis=1).max(axis=1)
    df['atr'] = tr.rolling(atr_period).mean()

    # Liquidity raid: price wicks above Asia high or below Asia low (not Asia session)
    sweep_dist = df['atr'] * min_sweep_pct * 1000  # Normalize sweep distance
    sweep_dist = np.maximum(sweep_dist, df['atr'] * 0.2)  # Minimum sweep = 0.2× ATR

    df['raid_high'] = (df['high'] > df['asia_h']) & (~df['is_asia'])
    df['raid_high'] = df['raid_high'] & ((df['high'] - df['asia_h']) > sweep_dist)

    df['raid_low'] = (df['low'] < df['asia_l']) & (~df['is_asia'])
    df['raid_low'] = df['raid_low'] & ((df['asia_l'] - df['low']) > sweep_dist)

    # Market Structure Shift
    # Bearish MSS: close breaks below recent swing low (after raid_high)
    swing_low = df['low'].rolling(swing_period).min().shift(1)
    swing_high = df['high'].rolling(swing_period).max().shift(1)

    df['mss_bearish'] = df['close'] < swing_low
    df['mss_bullish'] = df['close'] > swing_high

    # Entry conditions
    # Short: raided Asia high, then MSS bearish, then price retraces back into Asia range
    df['short_entry'] = (
        df['raid_high'].shift(1) &
        df['mss_bearish'].shift(1) &
        (df['close'] < df['asia_h'])
    )

    # Long: raided Asia low, then MSS bullish, then price retraces back into Asia range
    df['long_entry'] = (
        df['raid_low'].shift(1) &
        df['mss_bullish'].shift(1) &
        (df['close'] > df['asia_l'])
    )

    # Generate signals
    signals = pd.Series(0, index=df.index)
    signals[df['long_entry']] = 1
    signals[df['short_entry']] = -1

    # Exit: opposite signal or ATR trailing stop
    atr = df['atr']
    ts_long = df['high'].rolling(swing_period).min() - atr * stop_mult
    ts_short = df['high'].rolling(swing_period).max() + atr * stop_mult

    stop_long = (df['close'].shift(1) < ts_long.shift(1))
    stop_short = (df['close'].shift(1) > ts_short.shift(1))

    signals[stop_long] = 0
    signals[stop_short] = 0

    # Flip: exit long on short signal and vice versa
    signals[(signals.shift(1) == 1) & (signals == -1)] = 0
    signals[(signals.shift(1) == -1) & (signals == 1)] = 0

    # Shift for look-ahead bias prevention
    signals = signals.shift(1)

    # Handle NaNs
    signals = signals.fillna(0).astype(int)

    # Validate
    assert len(signals) == len(df), f'Signal length mismatch: {len(signals)} vs {len(df)}'
    assert set(signals.unique()).issubset({-1, 0, 1}), f'Invalid signal values: {signals.unique()}'

    return signals
