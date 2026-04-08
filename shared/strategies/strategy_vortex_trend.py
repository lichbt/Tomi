# Strategy: Vortex Indicator Trend Confirmation
# Author: Strategy Coder Agent
# Edge: Directional movement via +VI/-VI cross — cleaner than ADX
# Libraries: pandas, numpy only

import pandas as pd
import numpy as np
from typing import Dict


def strategy_vortex_trend(
    df: pd.DataFrame,
    params: Dict[str, any]
) -> pd.Series:
    """
    Vortex Indicator trend confirmation strategy.

    Vortex captures directional movement:
      - +VI (Positive Vortex Index): upward movement strength
      - -VI (Negative Vortex Index): downward movement strength
    
    Entry rules:
      - Long:  +VI crosses above -VI AND price above ema_filter
      - Short: -VI crosses above +VI AND price below ema_filter
    Exit: cross back OR ATR trailing stop

    Args:
        df: OHLCV DataFrame
        params: {
            'vortex_period': int (default 14),
            'ema_filter': int (default 200),
            'atr_period': int (default 14),
            'stop_atr_mult': float (default 2.5),
            'adx_filter': bool (default False),
            'adx_period': int (default 14),
            'adx_thresh': float (default 20.0),
        }

    Returns:
        pd.Series of signals: +1 (long), -1 (short), 0 (flat)
    """
    required = {'open', 'high', 'low', 'close', 'volume'}
    if not required.issubset(df.columns):
        raise ValueError(f'Missing columns: {required - set(df.columns)}')

    vortex_period = params.get('vortex_period', 14)
    ema_filter_period = params.get('ema_filter', 200)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 2.5)
    use_adx = params.get('adx_filter', False)
    if use_adx:
        adx_period = params.get('adx_period', 14)
        adx_thresh = params.get('adx_thresh', 20.0)

    df = df.copy()

    # ── True Range ──
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift(1)).abs(),
        (df['low'] - df['close'].shift(1)).abs()
    ], axis=1).max(axis=1)

    # ── Vortex Components ──
    # TR+ = |High - Previous Low|
    tr_plus = (df['high'] - df['low'].shift(1)).abs()
    # TR- = |Low - Previous High|
    tr_minus = (df['low'] - df['high'].shift(1)).abs()

    # Vortex = rolling sum of movement / rolling sum of TR
    vi_plus = tr_plus.rolling(vortex_period).sum() / tr.rolling(vortex_period).sum()
    vi_minus = tr_minus.rolling(vortex_period).sum() / tr.rolling(vortex_period).sum()

    df['vi_plus'] = vi_plus
    df['vi_minus'] = vi_minus

    # ── Trend Filter: EMA ──
    df['ema'] = df['close'].ewm(span=ema_filter_period, adjust=False).mean()
    above_ema = df['close'] > df['ema']
    below_ema = df['close'] < df['ema']

    # ── ADX Filter (optional) ──
    if use_adx:
        # Simplified ADX
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        smoothed_tr = tr.rolling(adx_period).sum()
        plus_di = 100 * plus_dm.rolling(adx_period).sum() / smoothed_tr
        minus_di = 100 * minus_dm.rolling(adx_period).sum() / smoothed_tr
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
        adx = dx.rolling(adx_period).mean()
        df['adx'] = adx
        trending = adx > adx_thresh
    else:
        trending = True

    # ── Vortex Cross Signals ──
    # Long: +VI crosses above -VI (was below, now above)
    cross_up_long = (vi_plus.shift(1) < vi_minus.shift(1)) & (vi_plus > vi_minus)
    # Short: -VI crosses above +VI (was below, now above)
    cross_up_short = (vi_minus.shift(1) < vi_plus.shift(1)) & (vi_minus > vi_plus)

    # ── Entry Conditions ──
    long_entry = cross_up_long & above_ema
    short_entry = cross_up_short & below_ema

    if use_adx:
        long_entry = long_entry & trending
        short_entry = short_entry & trending

    df['long_entry'] = long_entry
    df['short_entry'] = short_entry

    # ── ATR Trailing Stop ──
    atr = tr.rolling(atr_period).mean()
    df['atr'] = atr

    # ── Generate Signals ──
    signals = pd.Series(0, index=df.index)
    signals[df['long_entry']] = 1
    signals[df['short_entry']] = -1

    # Exit on flip
    flip_long = signals.eq(1) & signals.shift(1).eq(-1)
    flip_short = signals.eq(-1) & signals.shift(1).eq(1)

    # Exit on ATR trailing stop
    ts_long = df['close'] - atr * stop_mult
    ts_short = df['close'] + atr * stop_mult

    stop_long = df['close'].shift(1) < ts_long.shift(1)
    stop_short = df['close'].shift(1) > ts_short.shift(1)

    # When trailing stop hits, set signal to 0
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
