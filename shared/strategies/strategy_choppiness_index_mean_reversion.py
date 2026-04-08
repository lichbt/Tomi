"""
Choppiness Index Mean Reversion Strategy
Source: QuantifiedStrategies (https://www.quantifiedstrategies.com/choppiness-index/)
Author: Tomi (Pipeline Manager) - direct implementation to unblock pipeline

Entry Conditions:
- Long: CHOP > 61.8, RSI < 30, ADX < 25
- Short: CHOP > 61.8, RSI > 70, ADX < 25

Exit Conditions:
- Long exit: CHOP < 50 OR RSI > 50
- Short exit: CHOP < 50 OR RSI < 50

All signals use .shift(1) to prevent look-ahead bias.
Vectorized implementation using pandas, numpy, pandas_ta.
"""

import pandas as pd
import numpy as np
import pandas_ta as ta
from typing import Tuple


def strategy_choppiness_index_mean_reversion(df: pd.DataFrame) -> pd.Series:
    """
    Generate trading signals for Choppiness Index Mean Reversion strategy.

    Args:
        df: DataFrame with columns ['high', 'low', 'close', 'volume']

    Returns:
        pd.Series with positions: 1 (long), -1 (short), 0 (flat)
    """
    # Parameter validation
    required_cols = {'high', 'low', 'close', 'volume'}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Input DataFrame missing required columns: {required_cols - set(df.columns)}")

    # Ensure index is sorted
    df = df.sort_index()

    # --- Indicator Calculations ---
    # 1. Choppiness Index (CHOP)
    N = 14
    atr_sum = ta.atr(df['high'], df['low'], df['close'], 1).rolling(N).sum()
    price_range = df['high'].rolling(N).max() - df['low'].rolling(N).min()
    chop = 100 * np.log10(atr_sum / price_range) / np.log10(N)

    # 2. ADX (trend strength filter)
    adx = ta.adx(df['high'], df['low'], df['close'], 14)['ADX_14']

    # 3. RSI (14-period)
    rsi = ta.rsi(df['close'], 14)

    # --- Entry Conditions ---
    long_entry = (chop > 61.8) & (rsi < 30) & (adx < 25)
    short_entry = (chop > 61.8) & (rsi > 70) & (adx < 25)

    # --- Exit Conditions ---
    # For longs: exit when chop < 50 OR rsi > 50
    # For shorts: exit when chop < 50 OR rsi < 50
    long_exit = (chop < 50) | (rsi > 50)
    short_exit = (chop < 50) | (rsi < 50)

    # --- Position Tracking ---
    # Use vectorized state tracking with shift to avoid look-ahead
    signals = pd.Series(0, index=df.index)
    position = 0

    for i in range(len(df)):
        if position == 1:  # currently long
            if long_exit.iloc[i]:
                position = 0
        elif position == -1:  # currently short
            if short_exit.iloc[i]:
                position = 0

        if position == 0:
            if long_entry.iloc[i]:
                position = 1
            elif short_entry.iloc[i]:
                position = -1

        signals.iloc[i] = position

    # Shift final signals by 1 to prevent look-ahead bias in backtest
    return signals.shift(1)


def strategy_choppiness_index_mean_reversion_stateful(df: pd.DataFrame) -> pd.Series:
    """
    Stateful version that tracks positions explicitly (used for clarity).
    Kept separate for reference but primary use is the simpler function above.
    """
    # Use the main implementation for consistency
    return strategy_choppiness_index_mean_reversion(df)


if __name__ == "__main__":
    print("Choppiness Index Mean Reversion Strategy")
    print("Import: from strategies.strategy_choppiness_index_mean_reversion import strategy_choppiness_index_mean_reversion")
    print("Ready for backtesting.")
