"""Z-Score Mean Reversion with Volatility Filter.

Author: Strategy Coder Agent

Core Logic:
  Z-Score = (close - SMA(200)) / StdDev(close, 200)
  Long: Z < -2 + low volatility (ATR/SMA < 20th percentile of 100-bar lookback).
  Short: Z > +2 + low volatility.
  Exit: Z reverts toward zero (>-0.5 for longs, <0.5 for shorts) OR max 20-bar hold.
  If volatility is HIGH: DO NOT enter (trend regime, mean reversion fails).
"""
from __future__ import annotations

import pandas as pd
import numpy as np


def _percentile_threshold(series: pd.Series, lookback: int, pct: float) -> pd.Series:
    """Rolling percentile threshold. Returns True when current value is below the pct-th percentile."""
    def _pct(x: np.ndarray) -> float:
        if len(x) < 2:
            return x[-1]
        return np.percentile(x, pct)

    threshold = series.rolling(lookback, min_periods=1).apply(_pct, raw=True)
    return series < threshold


def strategy_zscore_mean_reversion(
    df: pd.DataFrame, params: dict
) -> pd.Series[int]:
    """Z-score mean reversion with volatility regime filter.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: ['open', 'high', 'low', 'close', 'volume'].
    params : dict
        - sma_period : int, optional (default 200) — lookback for z-score
        - z_long_thresh : float, optional (default -2.0)
        - z_short_thresh : float, optional (default 2.0)
        - z_exit_long : float, optional (default -0.5) — revert threshold for longs
        - z_exit_short : float, optional (default 0.5) — revert threshold for shorts
        - max_hold_period : int, optional (default 20)
        - atr_period : int, optional (default 14)
        - vol_lookback : int, optional (default 100) — bars for volatility percentile
        - vol_pct_threshold : float, optional (default 20) — bottom Nth percentile = low vol

    Returns
    -------
    pd.Series
        Integer signals: 1 = long, -1 = short, 0 = flat.
        Shifted by 1 bar to prevent look-ahead bias.
    """
    # --- Extract columns ---------------------------------------------------------
    high = df["high"].astype(np.float64)
    low = df["low"].astype(np.float64)
    close = df["close"].astype(np.float64)

    # --- Parameters ---------------------------------------------------------------
    sma_period = params.get("sma_period", 200)
    z_long_thresh = params.get("z_long_thresh", -2.0)
    z_short_thresh = params.get("z_short_thresh", 2.0)
    z_exit_long = params.get("z_exit_long", -0.5)
    z_exit_short = params.get("z_exit_short", 0.5)
    max_hold_period = params.get("max_hold_period", 20)
    atr_period = params.get("atr_period", 14)
    vol_lookback = params.get("vol_lookback", 100)
    vol_pct_threshold = params.get("vol_pct_threshold", 20)

    # --- Z-Score -----------------------------------------------------------------
    sma200 = close.rolling(sma_period).mean()
    std200 = close.rolling(sma_period).std(ddof=0)
    z_score = (close - sma200) / (std200 + 1e-9)

    # --- Volatility filter --------------------------------------------------------
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    vol_ratio = atr / (sma200 + 1e-9)
    vol_low = _percentile_threshold(vol_ratio, vol_lookback, vol_pct_threshold)

    # --- Entry conditions (vectorized) -------------------------------------------
    long_entry = (z_score < z_long_thresh) & vol_low
    short_entry = (z_score > z_short_thresh) & vol_low

    # --- Exit conditions (vectorized) --------------------------------------------
    exit_long_z = z_score > z_exit_long
    exit_short_z = z_score < z_exit_short

    # --- Signal generation loop (stateful for max-hold) --------------------------
    signals = pd.Series(0, index=df.index)
    position = 0
    bars_held = 0

    lookback = max(sma_period, atr_period, vol_lookback)

    for i in range(lookback, len(df)):
        if pd.isna(z_score.iloc[i]) or pd.isna(vol_ratio.iloc[i]):
            signals.iloc[i] = position
            continue

        cur_high = high.iloc[i]
        cur_low = low.iloc[i]
        cur_close = close.iloc[i]
        cur_z = z_score.iloc[i]

        # --- Exit logic ----------------------------------------------------------
        if position == 1:  # Long
            if exit_long_z.iloc[i] or bars_held >= max_hold_period:
                position = 0
                bars_held = 0
            else:
                bars_held += 1
        elif position == -1:  # Short
            if exit_short_z.iloc[i] or bars_held >= max_hold_period:
                position = 0
                bars_held = 0
            else:
                bars_held += 1

        # --- Entry (only when flat) -----------------------------------------------
        if position == 0:
            if long_entry.iloc[i]:
                position = 1
                bars_held = 0
            elif short_entry.iloc[i]:
                position = -1
                bars_held = 0

        signals.iloc[i] = position

    return signals.astype(int).shift(1).fillna(0).astype(int)
