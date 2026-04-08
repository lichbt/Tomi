"""
Strategy: LliterH Mean Reversion
Author: Strategy Coder Agent

A long-only mean reversion strategy validated on H4 and Daily timeframes
for SPX, NASDAQ, and Gold (XAUUSD).

Logic:
    Entry conditions (all must be true):
    1. Price below volatility-adjusted floor:
       floor = Highest(High, period) - (mult * SMA(High - Low, range_period))
    2. IBS (Internal Bar Strength) < threshold:
       IBS = (Close - Low) / (High - Low)
    3. Regime filter: Close > SMA(period) (uptrend only)

    Exit conditions:
    - Leg 1 (partial): Close crosses above exit_sma
    - Leg 2 (remainder): ATR-based trailing stop or hard stop
"""

import numpy as np
import pandas as pd
from typing import Dict


def strategy_lliterh_mean_reversion(
    df: pd.DataFrame,
    params: Dict[str, float] = None,
) -> pd.Series:
    """
    Generate long-only mean reversion signals using LliterH logic.

    Args:
        df: OHLCV DataFrame with columns ['open', 'high', 'low', 'close', 'volume'].
        params: Strategy parameters:
            - floor_high_period: Lookback for highest high (default 10)
            - floor_mult: Multiplier for ATR-like range (default 2.5)
            - floor_range_period: Period for SMA of range (default 25)
            - ibs_threshold: Max IBS value for entry (default 0.30)
            - regime_sma: SMA period for trend filter (default 50)
            - exit_sma: SMA period for partial exit (default 20)
            - atr_period: ATR calculation period (default 14)
            - stop_atr_mult: ATR multiplier for stop loss (default 2.0)

    Returns:
        pd.Series: Signal values +1 (long), 0 (flat). Index matches input df.
    """
    if params is None:
        params = {}

    # Unpack parameters with defaults
    floor_high_period = int(params.get("floor_high_period", 10))
    floor_mult = float(params.get("floor_mult", 2.5))
    floor_range_period = int(params.get("floor_range_period", 25))
    ibs_threshold = float(params.get("ibs_threshold", 0.30))
    regime_sma = int(params.get("regime_sma", 50))
    exit_sma = int(params.get("exit_sma", 20))
    atr_period = int(params.get("atr_period", 14))
    stop_atr_mult = float(params.get("stop_atr_mult", 2.0))

    # Input validation
    required_cols = ["open", "high", "low", "close", "volume"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    high = df["high"].astype(np.float64)
    low = df["low"].astype(np.float64)
    close = df["close"].astype(np.float64)
    open_ = df["open"].astype(np.float64)

    n = len(df)
    signals = pd.Series(0, index=df.index, dtype=np.int8)

    # --- Vectorized indicator calculations ---

    # Volatility-Adjusted Floor
    highest_high = high.rolling(window=floor_high_period, min_periods=1).max()
    price_range = high - low
    sma_range = price_range.rolling(window=floor_range_period, min_periods=1).mean()
    floor = highest_high - (floor_mult * sma_range)

    # IBS (Internal Bar Strength)
    ibs_denominator = high - low
    ibs = np.where(ibs_denominator > 0, (close - low) / ibs_denominator, 0.5)
    ibs = pd.Series(ibs, index=df.index)

    # Regime Filter (SMA)
    regime_sma_series = close.rolling(window=regime_sma, min_periods=1).mean()

    # Exit SMA
    exit_sma_series = close.rolling(window=exit_sma, min_periods=1).mean()

    # ATR (Wilder's smoothing)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(span=atr_period, adjust=False, min_periods=atr_period).mean()

    # --- Entry Conditions (Vectorized) ---
    # 1. Price below floor
    cond_floor = close < floor
    # 2. IBS < threshold
    cond_ibs = ibs < ibs_threshold
    # 3. Regime filter (uptrend)
    cond_regime = close > regime_sma_series

    # Raw entry signal
    entry_signal = cond_floor & cond_ibs & cond_regime

    # --- Exit Logic (Position-Holding Loop) ---
    # Since exits depend on position state (trailing stop, partial fills),
    # we use a loop here as requested.

    position = 0  # 0 = flat, 1 = long, 2 = half-long (after leg 1 exit)
    entry_price = 0.0
    highest_close_since_entry = 0.0
    leg1_exited = False

    for i in range(n):
        idx = df.index[i]
        current_close = close.iloc[i]
        current_high = high.iloc[i]
        current_low = low.iloc[i]
        current_atr = atr.iloc[i] if not pd.isna(atr.iloc[i]) else 0.0
        current_exit_sma = exit_sma_series.iloc[i]

        if position == 0:
            # Look for entry
            if entry_signal.iloc[i]:
                position = 1
                signals.iloc[i] = 1
                entry_price = current_close
                highest_close_since_entry = current_close
                leg1_exited = False
            else:
                signals.iloc[i] = 0

        elif position == 1:
            # Full long position
            # Update highest close for trailing stop
            if current_close > highest_close_since_entry:
                highest_close_since_entry = current_close

            # Check Leg 1 Exit: Close crosses above exit_sma
            if not leg1_exited and current_close > current_exit_sma:
                # Partial exit: move to half position (represented as 1 for signal, but logic changes)
                # For signal series, we stay long (1) but mark leg1_exited
                leg1_exited = True
                signals.iloc[i] = 1
                # Note: In a real backtester, this would reduce position size by 50%
                # Here we keep signal=1 but change internal state to track remaining exit

            # Check Hard Stop / Trailing Stop
            # Trailing stop level based on highest close since entry
            trailing_stop = highest_close_since_entry - (stop_atr_mult * current_atr)
            # Hard stop based on entry price
            hard_stop = entry_price - (stop_atr_mult * current_atr)
            # Use the tighter (higher) stop for safety
            effective_stop = max(trailing_stop, hard_stop)

            if current_close < effective_stop:
                position = 0
                signals.iloc[i] = 0
                entry_price = 0.0
                leg1_exited = False
                highest_close_since_entry = 0.0
            else:
                signals.iloc[i] = 1

        else:
            # Should not reach here in long-only logic
            signals.iloc[i] = 0

    # Final validation
    assert len(signals) == len(df), "Signal length must match DataFrame length"
    assert set(signals.unique()).issubset({-1, 0, 1}), "Signals must be in {-1, 0, 1}"

    # Shift signal by 1 to prevent look-ahead bias (enter at next open)
    signals = signals.shift(1).fillna(0).astype(np.int8)

    return signals
