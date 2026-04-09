"""
Strategy 10: ATR-Scaled Mean Reversion (Triple MA)
Status: 🧪 Ready for Backtesting
Source: James Ford — "MA+ATR Mean Reversion" (pyhood)
URL: https://jamestford.github.io/pyhood/strategies/ma-atr-mean-reversion/
"""

import pandas as pd
import numpy as np
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange as ATRIndicator


def strategy_atr_scaled_mean_reversion(
    df: pd.DataFrame,
    ema_fast_period: int = 10,
    ema_med_period: int = 50,
    ema_long_period: int = 200,
    atr_period: int = 14,
    atr_multiplier: float = 2.0,
    min_hold_bars: int = 2
) -> pd.Series:
    """
    ATR-Scaled Mean Reversion strategy using Triple EMA + ATR bands.
    
    Trend Confirmation: EMA(10) > EMA(50) > EMA(200) for uptrend
    Entry: Price pulls back to EMA(10) and dips below lower ATR band → long
    Exit: Price reverts to EMA(10)
    
    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        ema_fast_period: Fast EMA period
        ema_med_period: Medium EMA period
        ema_long_period: Slow EMA period
        atr_period: ATR period
        atr_multiplier: ATR multiplier for band width
        min_hold_bars: Minimum bars to hold position
    
    Returns:
        pd.Series with signals: 1 (long), -1 (short), 0 (flat)
    """
    df = df.copy()
    
    # Compute EMAs
    df['ema_fast'] = EMAIndicator(df['close'], window=ema_fast_period).ema_indicator()
    df['ema_med'] = EMAIndicator(df['close'], window=ema_med_period).ema_indicator()
    df['ema_long'] = EMAIndicator(df['close'], window=ema_long_period).ema_indicator()
    
    # Compute ATR
    df['atr'] = ATRIndicator(df['high'], df['low'], df['close'], window=atr_period).average_true_range()
    
    # Compute bands
    df['lower_band'] = df['ema_fast'] - (df['atr'] * atr_multiplier)
    df['upper_band'] = df['ema_fast'] + (df['atr'] * atr_multiplier)
    
    # Trend direction (lagged to avoid lookahead)
    df['ema_fast_lag'] = df['ema_fast'].shift(1)
    df['ema_med_lag'] = df['ema_med'].shift(1)
    df['ema_long_lag'] = df['ema_long'].shift(1)
    df['lower_band_lag'] = df['lower_band'].shift(1)
    df['upper_band_lag'] = df['upper_band'].shift(1)
    df['close_lag'] = df['close'].shift(1)
    df['close_prev'] = df['close'].shift(2)
    
    # Uptrend: EMA(10) > EMA(50) > EMA(200)
    df['uptrend'] = (
        (df['ema_fast_lag'] > df['ema_med_lag']) & 
        (df['ema_med_lag'] > df['ema_long_lag'])
    )
    
    # Downtrend: EMA(10) < EMA(50) < EMA(200)
    df['downtrend'] = (
        (df['ema_fast_lag'] < df['ema_med_lag']) & 
        (df['ema_med_lag'] < df['ema_long_lag'])
    )
    
    # Entry signals with shift(1) to avoid lookahead
    df['signal'] = 0
    
    # Long entry: in uptrend, price was above lower band, now crosses below
    long_entry = (
        df['uptrend'].shift(1) &
        (df['close_prev'] >= df['lower_band_lag']) &
        (df['close_lag'] < df['lower_band_lag'])
    )
    df.loc[long_entry, 'signal'] = 1
    
    # Short entry: in downtrend, price was below upper band, now crosses above
    short_entry = (
        df['downtrend'].shift(1) &
        (df['close_prev'] <= df['upper_band_lag']) &
        (df['close_lag'] > df['upper_band_lag'])
    )
    df.loc[short_entry, 'signal'] = -1
    
    # Maintain position
    df['position'] = df['signal'].replace(0, np.nan).ffill().fillna(0)
    
    # Track bars in position for minimum hold
    df['bars_in_trade'] = df.groupby((df['position'] != df['position'].shift(1)).cumsum()).cumcount()
    
    # Long exit: price reverts to EMA(10) AND min hold satisfied
    df.loc[
        (df['position'] == 1) & 
        (df['bars_in_trade'] >= min_hold_bars) &
        (df['close_lag'] > df['ema_fast_lag']),
        'position'
    ] = 0
    
    # Short exit: price reverts to EMA(10) AND min hold satisfied
    df.loc[
        (df['position'] == -1) & 
        (df['bars_in_trade'] >= min_hold_bars) &
        (df['close_lag'] < df['ema_fast_lag']),
        'position'
    ] = 0
    
    return df['position'].shift(1).fillna(0).astype(int)
