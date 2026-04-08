"""
Moving Average Crossover with SMA Trend Filter, ATR Stops, and Trailing Exit.

Enhanced version with risk management.
"""

from typing import Dict
import pandas as pd
import numpy as np
from data.fetcher import get_real_data


def ta_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """Average True Range."""
    tr = pd.concat([
        high - low,
        abs(high - close.shift(1)),
        abs(low - close.shift(1))
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def strategy_ma_crossover_v2(
    df: pd.DataFrame,
    params: Dict
) -> pd.Series:
    """
    MA Crossover with SMA200 trend filter, ATR stops, and trailing exit.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data with columns: open, high, low, close, volume
    params : dict
        'fast_period': int (default 10)
        'slow_period': int (default 30)
        'sma_filter': int (default 200) - SMA trend filter period
        'atr_period': int (default 14) - ATR calculation period
        'stop_atr_mult': float (default 2.0) - ATR multiplier for stop loss
        'trail_atr_mult': float (default 1.5) - ATR multiplier for trailing stop
        'breakeven_atr': float (default 1.0) - Move stop to breakeven after N * ATR profit

    Returns
    -------
    pd.Series : +1 (long), -1 (short), 0 (flat)
    """
    fast = params.get('fast_period', 10)
    slow = params.get('slow_period', 30)
    sma_filter = params.get('sma_filter', 200)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 2.0)
    trail_mult = params.get('trail_atr_mult', 1.5)
    be_mult = params.get('breakeven_atr', 1.0)

    close = df['close']
    high = df['high']
    low = df['low']

    # Moving averages
    fast_ma = close.rolling(fast).mean()
    slow_ma = close.rolling(slow).mean()
    sma200 = close.rolling(sma_filter).mean()

    # ATR
    atr = ta_atr(high, low, close, atr_period)

    # Raw crossover signals
    cross_up = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
    cross_down = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))

    # Trend filter
    long_allowed = close > sma200
    short_allowed = close < sma200

    # Initialize
    signals = pd.Series(0, index=df.index)
    position = 0  # 0=flat, 1=long, -1=short
    entry_price = 0.0
    stop_price = 0.0
    highest_since_entry = 0.0
    lowest_since_entry = float('inf')

    for i in range(sma_filter, len(df)):
        current_close = close.iloc[i]
        current_high = high.iloc[i]
        current_low = low.iloc[i]
        current_atr = atr.iloc[i]

        if pd.isna(current_atr) or current_atr <= 0:
            signals.iloc[i] = signals.iloc[i-1] if i > 0 else 0
            continue

        # --- Exit Logic ---
        if position == 1:  # Long position
            # Update highest price
            highest_since_entry = max(highest_since_entry, current_high)

            # Trailing stop: trail behind highest by trail_mult * ATR
            trail_stop = highest_since_entry - trail_mult * current_atr

            # Breakeven: move stop to entry + small buffer after be_mult * ATR profit
            if current_close - entry_price >= be_mult * current_atr:
                trail_stop = max(trail_stop, entry_price + 0.5 * current_atr)

            # Use the tighter of initial stop and trailing stop
            effective_stop = max(stop_price, trail_stop)

            # Check exit
            if current_low <= effective_stop:
                signals.iloc[i] = 0
                position = 0

        elif position == -1:  # Short position
            # Update lowest price
            lowest_since_entry = min(lowest_since_entry, current_low)

            # Trailing stop: trail above lowest by trail_mult * ATR
            trail_stop = lowest_since_entry + trail_mult * current_atr

            # Breakeven
            if entry_price - current_close >= be_mult * current_atr:
                trail_stop = min(trail_stop, entry_price - 0.5 * current_atr)

            effective_stop = min(stop_price, trail_stop)

            if current_high >= effective_stop:
                signals.iloc[i] = 0
                position = 0

        # --- Entry Logic ---
        if position == 0:
            if cross_up.iloc[i] and long_allowed.iloc[i]:
                signals.iloc[i] = 1
                position = 1
                entry_price = current_close
                stop_price = entry_price - stop_mult * current_atr
                highest_since_entry = current_high
            elif cross_down.iloc[i] and short_allowed.iloc[i]:
                signals.iloc[i] = -1
                position = -1
                entry_price = current_close
                stop_price = entry_price + stop_mult * current_atr
                lowest_since_entry = current_low
        elif position != 0:
            # Hold position
            signals.iloc[i] = position

    return signals


def generate_sample_data(n_periods: int = 500) -> pd.DataFrame:
    """Synthetic data fallback."""
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.02, n_periods)
    close = 100 * np.exp(np.cumsum(returns))
    volatility = 0.01 * close
    high = close + np.abs(np.random.normal(0, volatility))
    low = close - np.abs(np.random.normal(0, volatility))
    open_price = close + np.random.normal(0, volatility * 0.5)
    volume = np.random.randint(1000, 10000, n_periods)
    return pd.DataFrame({'open': open_price, 'high': high, 'low': low, 'close': close, 'volume': volume})


def main() -> None:
    """Demo runner."""
    print("=" * 60)
    print("MA Crossover V2 with SMA Filter + ATR Stops + Trailing")
    print("=" * 60)

    print("\n1. Fetching market data...")
    try:
        df = get_real_data(instrument="EUR_USD", granularity="H1", days=90, use_cache=True)
    except Exception as e:
        print(f"   Fetch failed: {e}. Using synthetic.")
        df = generate_sample_data(500)

    print(f"   Rows: {len(df)}")

    params = {
        'fast_period': 10,
        'slow_period': 30,
        'sma_filter': 200,
        'atr_period': 14,
        'stop_atr_mult': 2.0,
        'trail_atr_mult': 1.5,
        'breakeven_atr': 1.0
    }

    signals = strategy_ma_crossover_v2(df, params)
    n = (signals != 0).sum()
    print(f"\n2. Signals: {n} ({(signals==1).sum()} long, {(signals==-1).sum()} short)")
    print("=" * 60)


if __name__ == "__main__":
    main()
