"""Bollinger-Keltner Squeeze Breakout.

Author: Strategy Coder Agent

Core Logic:
  - Squeeze detected when Bollinger Bands contract inside Keltner Channels.
  - Entry long: Close breaks above upper Keltner after squeeze ends + volume spike.
  - Entry short: Close breaks below lower Keltner after squeeze ends.
  - Exit: 3x ATR trailing stop, or price closes back inside Bollinger Bands.
"""
from __future__ import annotations

import pandas as pd
import numpy as np


def strategy_bollinger_keltner_squeeze(
    df: pd.DataFrame, params: dict
) -> pd.Series[int]:
    """Bollinger-Keltner squeeze breakout with ATR trailing stop.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: ['open', 'high', 'low', 'close', 'volume'].
    params : dict
        - bb_period : int, optional (default 20)
        - bb_std : float, optional (default 2.0)
        - kc_period : int, optional (default 20)
        - kc_atr_mult : float, optional (default 1.5)
        - vol_ma_period : int, optional (default 20)
        - vol_spike_mult : float, optional (default 1.2)
        - atr_period : int, optional (default 14)
        - stop_atr_mult : float, optional (default 3.0)

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
    volume = df["volume"].astype(np.float64)

    # --- Parameters ---------------------------------------------------------------
    bb_period = params.get("bb_period", 20)
    bb_std = params.get("bb_std", 2.0)
    kc_period = params.get("kc_period", 20)
    kc_atr_mult = params.get("kc_atr_mult", 1.5)
    vol_ma_period = params.get("vol_ma_period", 20)
    vol_spike_mult = params.get("vol_spike_mult", 1.2)
    atr_period = params.get("atr_period", 14)
    stop_atr_mult = params.get("stop_atr_mult", 3.0)

    # --- Bollinger Bands ----------------------------------------------------------
    bb_mid = close.rolling(bb_period).mean()
    bb_std_dev = close.rolling(bb_period).std(ddof=0)
    bb_upper = bb_mid + bb_std * bb_std_dev
    bb_lower = bb_mid - bb_std * bb_std_dev

    # --- ATR ---------------------------------------------------------------------
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    # --- Keltner Channels ---------------------------------------------------------
    kc_mid = close.rolling(kc_period).mean()  # ema approximated by sma for simplicity
    kc_upper = kc_mid + kc_atr_mult * atr
    kc_lower = kc_mid - kc_atr_mult * atr

    # --- Squeeze detection --------------------------------------------------------
    squeeze = (bb_upper < kc_upper) & (bb_lower > kc_lower)
    squeeze_just_ended = squeeze.shift(1) & (~squeeze)

    # --- Volume filter ------------------------------------------------------------
    vol_ma = volume.rolling(vol_ma_period).mean()
    vol_spike = volume > vol_spike_mult * vol_ma

    # --- Entry signals ------------------------------------------------------------
    long_entry = squeeze_just_ended & (close > kc_upper) & vol_spike
    short_entry = squeeze_just_ended & (close < kc_lower) & vol_spike

    # --- Exit: back inside Bollinger Bands ----------------------------------------
    exit_long = close < bb_upper  # closes back inside upper BB
    exit_short = close > bb_lower  # closes back inside lower BB

    # --- Signal generation loop ---------------------------------------------------
    signals = pd.Series(0, index=df.index)
    position = 0
    peak = 0.0
    trough = 0.0

    lookback = max(bb_period, kc_period, atr_period, vol_ma_period)

    for i in range(lookback, len(df)):
        if pd.isna(atr.iloc[i]) or atr.iloc[i] <= 0:
            signals.iloc[i] = position
            continue

        cur_high = high.iloc[i]
        cur_low = low.iloc[i]
        cur_close = close.iloc[i]
        cur_atr = atr.iloc[i]

        # --- Trailing stop exit --------------------------------------------------
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
