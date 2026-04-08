"""
Strategy: Linear Regression Hook (Daily/H4)
Author: Strategy Coder Agent
Source: algomatictrading.com — 74.2% WR, 298 trades, MAR 0.22 on SPX Daily

Description:
    Mean reversion strategy using linear regression slope hook.
    Entry: LR slope hooks up (was declining yesterday) + price < SMA + (optionally not Friday)
    Exit: Close >= upper ATR band (TP) OR close < lower ATR band (SL)
          OR LR slope turns negative OR max hold bars

Parameters:
    lr_period: int (default=3) — Linear regression lookback period
    sma_period: int (default=200) — SMA period for trend filter
    tp_atr_mult: float (default=2.0) — ATR multiplier for take-profit band
    sl_atr_mult: float (default=2.0) — ATR multiplier for stop-loss band
    max_hold: int (default=15) — Maximum bars to hold position
    skip_friday: bool (default=True) — Whether to skip Friday entries
    atr_period: int (default=14) — ATR lookback period
"""

from typing import Optional

import numpy as np
import pandas as pd


def _compute_atr_vectorized(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Compute ATR using vectorized operations."""
    n = len(high)
    prev_close = np.empty(n)
    prev_close[0] = close[0]
    prev_close[1:] = close[:-1]
    
    tr = np.maximum(
        np.maximum(high - low, np.abs(high - prev_close)),
        np.abs(low - prev_close)
    )
    
    atr = np.empty(n)
    atr[:period] = np.nan
    atr[period] = np.mean(tr[1:period+1])  # First valid ATR
    
    # Use exponential moving average style for efficiency
    alpha = 1.0 / period
    for i in range(period + 1, n):
        atr[i] = atr[i-1] + alpha * (tr[i] - atr[i-1])
    
    return atr


def _compute_lr_slope_vectorized(close: np.ndarray, period: int) -> np.ndarray:
    """
    Compute linear regression slope using vectorized rolling window.
    Uses numpy stride tricks for efficient rolling window computation.
    """
    n = len(close)
    slopes = np.full(n, np.nan)
    
    if n < period:
        return slopes
    
    # Create rolling windows using stride tricks
    stride = close.strides[0] if hasattr(close, 'strides') else close.itemsize
    if hasattr(close, 'strides'):
        windows = np.lib.stride_tricks.as_strided(
            close, 
            shape=(n - period + 1, period),
            strides=(stride, stride)
        )
    else:
        # Fallback for plain ndarray
        windows = np.array([close[i:i+period] for i in range(n - period + 1)])
    
    x = np.arange(period, dtype=np.float64)
    x_mean = x.mean()
    denom = np.sum((x - x_mean) ** 2)
    
    if denom == 0:
        return slopes
    
    # Vectorized slope computation
    y_means = windows.mean(axis=1)
    numer = np.sum((x - x_mean) * (windows - y_means[:, np.newaxis]), axis=1)
    slopes[period-1:] = numer / denom
    
    return slopes


def strategy_linear_regression_hook(
    df: pd.DataFrame,
    params: Optional[dict] = None,
) -> pd.Series:
    """
    Generate position signals using Linear Regression Hook logic.
    Vectorized implementation for speed.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns ['open', 'high', 'low', 'close', 'volume'].
    params : dict, optional
        Override default parameters.

    Returns
    -------
    pd.Series
        Position signals: +1 (long), 0 (flat). Same index and length as df.
    """
    if params is None:
        params = {}

    lr_period: int = params.get("lr_period", 3)
    sma_period: int = params.get("sma_period", 200)
    tp_atr_mult: float = params.get("tp_atr_mult", 2.0)
    sl_atr_mult: float = params.get("sl_atr_mult", 2.0)
    max_hold: int = params.get("max_hold", 15)
    skip_friday: bool = params.get("skip_friday", True)
    atr_period: int = params.get("atr_period", 14)

    required_cols = {"open", "high", "low", "close", "volume"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    n = len(df)
    close = df["close"].values.astype(np.float64)
    high = df["high"].values.astype(np.float64)
    low = df["low"].values.astype(np.float64)

    # Compute ATR
    atr = _compute_atr_vectorized(high, low, close, atr_period)

    # Compute SMA
    sma = pd.Series(close).rolling(window=sma_period, min_periods=sma_period).mean().values

    # Compute LR slope (vectorized)
    lr_slope = _compute_lr_slope_vectorized(close, lr_period)

    # LR hook up: slope increasing
    lr_hook_up = np.roll(lr_slope > np.roll(lr_slope, 1), 1)
    lr_hook_up[:2] = False  # First 2 are invalid

    # Was declining: previous slope was lower or negative
    prev_slope = np.roll(lr_slope, 1)
    prev_prev_slope = np.roll(lr_slope, 2)
    was_declining = (prev_slope < prev_prev_slope) | (prev_slope < 0)
    was_declining[:2] = False

    # Friday filter
    if skip_friday:
        try:
            is_friday = df.index.dayofweek == 4
            not_friday = ~is_friday.values
        except AttributeError:
            not_friday = np.ones(n, dtype=bool)
    else:
        not_friday = np.ones(n, dtype=bool)

    # Entry condition
    price_below_sma = close < sma
    entry_signal = was_declining & lr_hook_up & price_below_sma & not_friday

    # ATR bands
    valid_atr = ~np.isnan(atr)
    upper_band = np.where(valid_atr, close + atr * tp_atr_mult, np.nan)
    lower_band = np.where(valid_atr, close - atr * sl_atr_mult, np.nan)

    # State machine for position management (still needs loop due to state)
    signals = np.zeros(n, dtype=np.int64)
    in_position = False
    entry_idx = -1

    for i in range(n):
        if not in_position:
            if entry_signal[i] and valid_atr[i] and not np.isnan(sma[i]):
                in_position = True
                entry_idx = i
                signals[i] = 1
        else:
            bars_held = i - entry_idx
            exit_cond = False

            # TP hit
            if close[i] >= upper_band[i]:
                exit_cond = True
            # SL hit
            elif close[i] < lower_band[i]:
                exit_cond = True
            # LR slope turns negative
            elif i >= 1 and lr_slope[i-1] >= 0 and lr_slope[i] < 0:
                exit_cond = True
            # Max hold
            elif bars_held >= max_hold:
                exit_cond = True

            if exit_cond:
                in_position = False
                entry_idx = -1
                signals[i] = 0
            else:
                signals[i] = 1

    return pd.Series(signals, index=df.index)
