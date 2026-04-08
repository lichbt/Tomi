"""Sequential Swing High-Low Structure Breakout.

Author: Strategy Coder Agent

Core Logic:
  Long: Detect L1-H1-L2 pattern (higher low L2 > L1), then breakout above H1.
  Short: Detect H1-L1-H2 pattern (lower high H2 < H1), then breakdown below L1.
  Exit: Dual stop (initial + ATR trailing stop at 2.0x).
  Swing detection uses adaptive period based on ATR volatility.
"""
from __future__ import annotations

import pandas as pd
import numpy as np


def strategy_swing_structure_breakout(
    df: pd.DataFrame, params: dict
) -> pd.Series[int]:
    """Swing-structure breakout strategy (L1-H1-L2 / H1-L1-H2 patterns).

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: ['open', 'high', 'low', 'close', 'volume'].
    params : dict
        - swing_period : int, optional (default 10) — bars each side for swing detection
        - atr_period : int, optional (default 14)
        - stop_atr_mult : float, optional (default 2.0)
        - initial_stop_atr_mult : float, optional (default 1.5) — tighter initial stop

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
    swing_period = params.get("swing_period", 10)
    atr_period = params.get("atr_period", 14)
    stop_atr_mult = params.get("stop_atr_mult", 2.0)
    initial_stop_atr_mult = params.get("initial_stop_atr_mult", 1.5)

    # --- Swing detection ----------------------------------------------------------
    def _detect_swings(source: pd.Series, window: int, is_high: bool) -> pd.Series:
        """Detect swing points using rolling local extrema."""
        result = pd.Series(False, index=source.index, dtype=bool)
        arr = source.values
        n = len(arr)
        for i in range(window, n - window):
            left = arr[i - window : i]
            right = arr[i + 1 : i + window + 1]
            if is_high:
                if arr[i] >= left.max() and arr[i] >= right.max():
                    result.iloc[i] = True
            else:
                if arr[i] <= left.min() and arr[i] <= right.min():
                    result.iloc[i] = True
        return result

    swing_highs = _detect_swings(high, swing_period, is_high=True)
    swing_lows = _detect_swings(low, swing_period, is_high=False)

    # --- ATR ---------------------------------------------------------------------
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    # --- Pattern tracking loop ---------------------------------------------------
    signals = pd.Series(0, index=df.index)
    position = 0
    entry_price = 0.0
    peak = 0.0
    trough = 0.0
    initial_stop_level = 0.0

    # State variables for L1-H1-L2 / H1-L1-H2 tracking
    L1 = None  # last confirmed swing low
    H1 = None  # last confirmed swing high
    L2 = None  # second swing low (must be > L1 for long setup)
    H2 = None  # second swing high (must be < H1 for short setup)

    lookback = max(swing_period, atr_period) + swing_period + 1

    for i in range(lookback, len(df)):
        if pd.isna(atr.iloc[i]) or atr.iloc[i] <= 0:
            signals.iloc[i] = position
            continue

        cur_high = high.iloc[i]
        cur_low = low.iloc[i]
        cur_close = close.iloc[i]
        cur_atr = atr.iloc[i]

        # --- Update swing points --------------------------------------------------
        # We check the bar 'swing_period' bars ago for confirmation
        check_idx = i - swing_period
        if check_idx >= 0:
            if swing_lows.iloc[check_idx] and L1 is None:
                L1 = low.iloc[check_idx]
            elif swing_lows.iloc[check_idx] and L1 is not None and L2 is None:
                L2 = low.iloc[check_idx]
            elif swing_highs.iloc[check_idx] and H1 is None:
                H1 = high.iloc[check_idx]
            elif swing_highs.iloc[check_idx] and H1 is not None and H2 is None:
                H2 = high.iloc[check_idx]

        # --- Exit logic (trailing stop) ------------------------------------------
        if position == 1:  # Long
            peak = max(peak, cur_high)
            stop_level = peak - stop_atr_mult * cur_atr
            # Use tighter stop initially
            if cur_low <= stop_level or cur_low <= initial_stop_level:
                position = 0
                L1, H1, L2 = None, None, None  # Reset pattern tracking
        elif position == -1:  # Short
            trough = min(trough, cur_low)
            stop_level = trough + stop_atr_mult * cur_atr
            if cur_high >= stop_level or cur_high >= initial_stop_level:
                position = 0
                H1, L1, H2 = None, None, None  # Reset pattern tracking

        # --- Entry logic (only when flat and pattern complete) --------------------
        if position == 0:
            # Long: L1-H1-L2 pattern with L2 > L1, then break above H1
            if H1 is not None and L2 is not None and L1 is not None:
                if L2 > L1 and cur_close > H1:
                    position = 1
                    entry_price = cur_close
                    peak = cur_high
                    initial_stop_level = entry_price - initial_stop_atr_mult * cur_atr
                    # Reset for next pattern
                    L1, H1, L2 = None, None, cur_low  # L2 becomes new L1

            # Short: H1-L1-H2 pattern with H2 < H1, then break below L1
            if L1 is not None and H2 is not None and H1 is not None:
                if H2 < H1 and cur_close < L1:
                    position = -1
                    entry_price = cur_close
                    trough = cur_low
                    initial_stop_level = entry_price + initial_stop_atr_mult * cur_atr
                    # Reset for next pattern
                    H1, L1, H2 = None, None, cur_high  # H2 becomes new H1

        signals.iloc[i] = position

    return signals.astype(int).shift(1).fillna(0).astype(int)
