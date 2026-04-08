"""
Strategy: IBS RSI Oversold (Daily/H4)
Author: Strategy Coder Agent
Source: algomatictrading.com — 42.2% WR, 2162 trades, MAR 0.47 on DAX 1H

Description:
    Mean reversion strategy using Internal Bar Strength (IBS) and RSI.
    Entry: IBS < 0.05 (closed near low) + RSI2 < 50 + BB Width < 0.06 (low vol)
    Exit: Close > 10 SMA OR ATR trailing stop OR max 20 bars

    IBS = (Close - Low) / (High - Low) — measures where the bar closed within its range.
    Low IBS means the price closed near the low (oversold).

Parameters:
    rsi_period: int (default=2) — RSI lookback period
    atr_period: int (default=14) — ATR lookback period
    atr_multiplier: float (default=2.0) — ATR trailing stop multiplier
    bb_period: int (default=20) — Bollinger Band lookback period
    bb_std: float (default=2.0) — Bollinger Band standard deviation multiplier
    max_bars: int (default=20) — Maximum bars to hold position
"""

from typing import Optional

import numpy as np
import pandas as pd


def _compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Compute Average True Range."""
    tr = np.empty_like(high)
    tr[0] = high[0] - low[0]
    for i in range(1, len(high)):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hc, lc)
    atr = np.empty_like(close)
    atr[:period - 1] = np.nan
    atr[period - 1] = np.mean(tr[:period])
    for i in range(period, len(tr)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def _compute_rsi(close: np.ndarray, period: int) -> np.ndarray:
    """
    Compute Wilder's RSI.

    Returns an array of RSI values, NaN for the first `period` values.
    """
    n = len(close)
    rsi = np.full(n, np.nan)

    if n < period + 1:
        return rsi

    deltas = np.diff(close)
    gain = np.where(deltas > 0, deltas, 0.0)
    loss = np.where(deltas < 0, -deltas, 0.0)

    # Initial average gain/loss
    avg_gain = np.mean(gain[:period])
    avg_loss = np.mean(loss[:period])

    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - (100.0 / (1.0 + rs))

    # Wilder's smoothing
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gain[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i - 1]) / period
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))

    return rsi


def strategy_ibs_rsi_oversold(
    df: pd.DataFrame,
    params: Optional[dict] = None,
) -> pd.Series:
    """
    Generate position signals using IBS + RSI2 oversold mean reversion logic.

    Uses a state machine to track position holding:
      - 0: flat (no position)
      - 1: in long position

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

    rsi_period: int = params.get("rsi_period", 2)
    atr_period: int = params.get("atr_period", 14)
    atr_multiplier: float = params.get("atr_multiplier", 2.0)
    bb_period: int = params.get("bb_period", 20)
    bb_std: float = params.get("bb_std", 2.0)
    max_bars: int = params.get("max_bars", 20)
    sma_period: int = params.get("sma_period", 10)

    # Validate required columns
    required_cols = {"open", "high", "low", "close", "volume"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    n = len(df)
    close = df["close"].values.astype(np.float64)
    high = df["high"].values.astype(np.float64)
    low = df["low"].values.astype(np.float64)
    open_ = df["open"].values.astype(np.float64)

    # Compute ATR
    atr = _compute_atr(high, low, close, atr_period)

    # Compute 10 SMA (exit reference)
    sma = pd.Series(close).rolling(window=sma_period, min_periods=sma_period).mean().values

    # Compute IBS: (Close - Low) / (High - Low)
    range_ = high - low
    ibs = np.where(range_ > 0, (close - low) / range_, 0.5)

    # Compute RSI2
    rsi2 = _compute_rsi(close, rsi_period)

    # Compute Bollinger Band Width: (Upper - Lower) / Middle
    middle = pd.Series(close).rolling(window=bb_period, min_periods=bb_period).mean().values
    std = pd.Series(close).rolling(window=bb_period, min_periods=bb_period).std().values
    upper_bb = middle + bb_std * std
    lower_bb = middle - bb_std * std
    bb_width = np.where(middle != 0, (upper_bb - lower_bb) / middle, 0.0)

    # Entry condition: IBS < 0.05 + RSI2 < 50 + BB Width < 0.06
    ibs_condition = ibs < 0.05
    rsi_condition = rsi2 < 50.0
    bb_condition = bb_width < 0.06

    entry_signal = ibs_condition & rsi_condition & bb_condition

    # State machine: position holding loop
    signals = np.zeros(n, dtype=np.int64)
    in_position = False
    entry_index = -1
    highest_close_since_entry = np.nan

    for i in range(n):
        if not in_position:
            # Check for entry
            if entry_signal[i] and not np.isnan(atr[i]) and not np.isnan(sma[i]):
                in_position = True
                entry_index = i
                highest_close_since_entry = close[i]
                signals[i] = 1
        else:
            # Already in position — check exit conditions
            bars_held = i - entry_index

            # Update highest close for trailing stop
            if close[i] > highest_close_since_entry:
                highest_close_since_entry = close[i]

            exit_condition = False

            # Close > 10 SMA
            if not np.isnan(sma[i]) and close[i] > sma[i]:
                exit_condition = True

            # ATR trailing stop: close < highest_close - atr * multiplier
            if not np.isnan(atr[i]):
                trailing_stop = highest_close_since_entry - atr[i] * atr_multiplier
                if close[i] < trailing_stop:
                    exit_condition = True

            # Max bars held
            if bars_held >= max_bars:
                exit_condition = True

            if exit_condition:
                in_position = False
                entry_index = -1
                signals[i] = 0
            else:
                signals[i] = 1

    return pd.Series(signals, index=df.index)
