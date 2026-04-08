"""Aroon + EMA Trend Strength Filter.

Author: Strategy Coder Agent

Core Logic:
  Long: Aroon Osc > 60 + price above 50 EMA + Aroon Up crosses above 70.
  Short: Aroon Osc < -60 + price below 50 EMA + Aroon Down crosses above 70.
  Exit: Aroon Osc crosses zero OR ATR trailing stop (2.5x default).
"""
from __future__ import annotations

import pandas as pd
import numpy as np


def _aroon(series: pd.Series, period: int, is_high: bool) -> pd.Series:
    """Compute Aroon Up or Aroon Down.

    Aroon Up  = (period - bars since highest high) / period * 100
    Aroon Down = (period - bars since lowest low) / period * 100
    """
    if is_high:
        # Bars since highest high in rolling window
        rolling_max_idx = series.rolling(period, min_periods=1).apply(
            lambda x: np.argmax(x), raw=True
        )
        aroon = (period - rolling_max_idx) / period * 100.0
    else:
        rolling_min_idx = series.rolling(period, min_periods=1).apply(
            lambda x: np.argmin(x), raw=True
        )
        aroon = (period - rolling_min_idx) / period * 100.0
    return aroon


def strategy_aroon_ema_trend(df: pd.DataFrame, params: dict) -> pd.Series[int]:
    """Aroon oscillator + EMA trend-filtered strategy.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: ['open', 'high', 'low', 'close', 'volume'].
    params : dict
        - aroon_period : int, optional (default 14)
        - ema_period : int, optional (default 50)
        - aroon_osc_thresh : float, optional (default 60) — abs value threshold
        - aroon_cross_level : float, optional (default 70)
        - atr_period : int, optional (default 14)
        - stop_atr_mult : float, optional (default 2.5)

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
    aroon_period = params.get("aroon_period", 14)
    ema_period = params.get("ema_period", 50)
    aroon_osc_thresh = params.get("aroon_osc_thresh", 60)
    aroon_cross_level = params.get("aroon_cross_level", 70)
    atr_period = params.get("atr_period", 14)
    stop_atr_mult = params.get("stop_atr_mult", 2.5)

    # --- Aroon -------------------------------------------------------------------
    aroon_up = _aroon(high, aroon_period, is_high=True)
    aroon_down = _aroon(low, aroon_period, is_high=False)
    aroon_osc = aroon_up - aroon_down

    # --- EMA trend filter ---------------------------------------------------------
    ema50 = close.ewm(span=ema_period, adjust=False).mean()

    # --- Aroon cross above 70 -----------------------------------------------------
    aroon_up_cross = (aroon_up.shift(1) < aroon_cross_level) & (
        aroon_up >= aroon_cross_level
    )
    aroon_down_cross = (aroon_down.shift(1) < aroon_cross_level) & (
        aroon_down >= aroon_cross_level
    )

    # --- ATR ---------------------------------------------------------------------
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    # --- Entry conditions (vectorized masks) -------------------------------------
    long_entry = (
        (aroon_osc > aroon_osc_thresh)
        & (close > ema50)
        & aroon_up_cross
    )
    short_entry = (
        (aroon_osc < -aroon_osc_thresh)
        & (close < ema50)
        & aroon_down_cross
    )

    # --- Exit: Aroon Osc crosses zero ---------------------------------------------
    exit_long = aroon_osc < 0
    exit_short = aroon_osc > 0

    # --- Signal generation loop ---------------------------------------------------
    signals = pd.Series(0, index=df.index)
    position = 0
    peak = 0.0
    trough = 0.0

    lookback = max(aroon_period, ema_period, atr_period) + 2

    for i in range(lookback, len(df)):
        if pd.isna(atr.iloc[i]) or atr.iloc[i] <= 0:
            signals.iloc[i] = position
            continue

        cur_high = high.iloc[i]
        cur_low = low.iloc[i]
        cur_atr = atr.iloc[i]

        # --- Exit logic (trailing stop + Aroon Osc zero cross) -------------------
        if position == 1:  # Long
            peak = max(peak, cur_high)
            stop_level = peak - stop_atr_mult * cur_atr
            if cur_low <= stop_level or exit_long.iloc[i]:
                position = 0
        elif position == -1:  # Short
            trough = min(trough, cur_low)
            stop_level = trough + stop_atr_mult * cur_atr
            if cur_high >= stop_level or exit_short.iloc[i]:
                position = 0

        # --- Entry (only when flat) -----------------------------------------------
        if position == 0:
            if long_entry.iloc[i]:
                position = 1
                peak = cur_high
            elif short_entry.iloc[i]:
                position = -1
                trough = cur_low

        signals.iloc[i] = position

    return signals.astype(int).shift(1).fillna(0).astype(int)
