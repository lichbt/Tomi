"""
Liquidity Sweep Reversal

Source: https://github.com/yeboster/liquidity-sweep-freqtrade
Indicators: Fibonacci OTE (62%-79%), Swing detection, Fair Value Gap (FVG), HTF Market Structure (BoS)
"""

import pandas as pd
import numpy as np

def find_swing_highs(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Detect swing highs (local maxima)."""
    highs = df['high'].rolling(window, center=True).max()
    swing_mask = df['high'] == highs
    return swing_mask

def find_swing_lows(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Detect swing lows (local minima)."""
    lows = df['low'].rolling(window, center=True).min()
    swing_mask = df['low'] == lows
    return swing_mask

def detect_fvg(candles: pd.DataFrame, lookback: int = 3) -> pd.Series:
    """
    Fair Value Gap: when candle's low is higher than previous candle's high (bull FVG)
    or candle's high is lower than next candle's low (bear FVG).
    Returns a series of FVG levels.
    """
    fvg_bull = (candles['low'] > candles['high'].shift(1))
    fvg_bear = (candles['high'] < candles['low'].shift(-1))
    fvg_zones = pd.Series(0, index=candles.index)
    fvg_zones[fvg_bull] = 1
    fvg_zones[fvg_bear] = -1
    return fvg_zones

def strategy_liquiditysweepreversal(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """
    Liquidity sweep reversal based on OTE Fibonacci zones and market structure.

    Parameters
    ----------
    df : pd.DataFrame with OHLCV, must be 15m timeframe
    params : dict
        'ote_lower' : 0.62 (default)
        'ote_upper' : 0.79 (default)
        'swing_window' : 20 (default)
        'min_rr' : 2.0 (minimum risk:reward, used for filtering)

    Returns
    -------
    pd.Series : +1 (long), -1 (short), 0 (flat)
    """
    p = params or {}
    ote_lower = p.get('ote_lower', 0.62)
    ote_upper = p.get('ote_upper', 0.79)
    swing_window = p.get('swing_window', 20)

    close = df['close']
    high = df['high']
    low = df['low']

    # Detect swings
    swing_highs = find_swing_highs(df, swing_window)
    swing_lows = find_swing_lows(df, swing_window)

    signals = pd.Series(0, index=df.index)
    in_long = False
    in_short = False

    # Simplified entry logic (without full HTF context for now)
    for i in range(swing_window, len(df)):
        # Identify recent swing high and low for OTE calculation
        recent_high_idx = high.iloc[i-swing_window:i][swing_highs.iloc[i-swing_window:i]].index[-1] if swing_highs.iloc[i-swing_window:i].any() else None
        recent_low_idx = low.iloc[i-swing_window:i][swing_lows.iloc[i-swing_window:i]].index[-1] if swing_lows.iloc[i-swing_window:i].any() else None

        if recent_high_idx is None or recent_low_idx is None:
            continue

        ext_range_high = high.loc[recent_high_idx]
        ext_range_low = low.loc[recent_low_idx]
        range_size = ext_range_high - ext_range_low

        current_price = close.iloc[i]
        current_high = high.iloc[i]

        # Short setup: price in OTE premium zone (62-79% retracement from high to low)
        fib_ratio = (ext_range_high - current_price) / range_size
        if ote_lower <= fib_ratio <= ote_upper:
            # Check for sweep above recent swing high
            recent_local_high = high.iloc[i-swing_window:i].max()
            if current_high > recent_local_high:
                # Price swept above swing high
                # Look for close below triggering low
                triggering_low = low.iloc[i-swing_window:i].min()
                if current_price < triggering_low:
                    signals.iloc[i] = -1
                    in_short = True

        # Long setup (mirror)
        fib_ratio_long = (current_price - ext_range_low) / range_size
        if ote_lower <= fib_ratio_long <= ote_upper:
            recent_local_low = low.iloc[i-swing_window:i].min()
            if current_price < recent_local_low:  # Sweep below
                triggering_high = high.iloc[i-swing_window:i].max()
                if current_price > triggering_high:
                    signals.iloc[i] = 1
                    in_long = True

    return signals