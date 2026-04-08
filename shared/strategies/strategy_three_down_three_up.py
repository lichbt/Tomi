"""
Strategy: 3 Down 3 Up (Daily/H4)
Author: Strategy Coder Agent
Source: algomatictrading.com — 75% WR, 283 trades, MAR 0.40 on NAS100 Daily

Description:
    Long-only mean reversion strategy for indices.
    Entry: 3 consecutive bearish bars + 3rd bar body > 1.5× avg body + close < 50 SMA
    Exit: 3 consecutive bullish bars OR close > 50 SMA OR ATR trailing stop OR max 20 bars

Parameters:
    atr_period: int (default=14) — ATR lookback period
    atr_multiplier: float (default=2.0) — ATR trailing stop multiplier
    avg_body_period: int (default=10) — Average body size lookback
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


def strategy_three_down_three_up(
    df: pd.DataFrame,
    params: Optional[dict] = None,
) -> pd.Series:
    """
    Generate position signals using the 3 Down 3 Up mean reversion logic.

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

    atr_period: int = params.get("atr_period", 14)
    atr_multiplier: float = params.get("atr_multiplier", 2.0)
    avg_body_period: int = params.get("avg_body_period", 10)
    max_bars: int = params.get("max_bars", 20)
    sma_period: int = params.get("sma_period", 50)

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

    # Compute 50 SMA
    sma = pd.Series(close).rolling(window=sma_period, min_periods=sma_period).mean().values

    # Compute average body size
    body = np.abs(close - open_)
    avg_body = pd.Series(body).rolling(
        window=avg_body_period, min_periods=avg_body_period
    ).mean().values

    # Detect 3 consecutive bearish bars
    bearish = close < open_
    three_bearish = (
        bearish
        & np.roll(bearish, 1)
        & np.roll(bearish, 2)
    )
    three_bearish[:2] = False  # First 2 bars cannot have 3 consecutive

    # 3rd bar body > 1.5 × average body
    body_condition = body > 1.5 * avg_body

    # Close below 50 SMA
    below_sma = close < sma

    # Entry condition: all three must be true
    entry_signal = three_bearish & body_condition & below_sma

    # Detect 3 consecutive bullish bars (exit condition)
    bullish = close > open_
    three_bullish = (
        bullish
        & np.roll(bullish, 1)
        & np.roll(bullish, 2)
    )
    three_bullish[:2] = False

    # Exit conditions: 3 bullish OR close > SMA OR ATR trailing stop hit
    above_sma = close > sma

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

            # 3 consecutive bullish bars
            if three_bullish[i]:
                exit_condition = True

            # Close above SMA
            if above_sma[i]:
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
