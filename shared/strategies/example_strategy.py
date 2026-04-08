"""
Moving Average Crossover Strategy

A classic trend-following strategy that generates buy/sell signals based on
the crossover of fast and slow moving averages.

Entry Rules:
- Long (+1): Fast MA crosses above Slow MA
- Short (-1): Fast MA crosses below Slow MA
- Flat (0): No crossover

The strategy is vectorized and works on pandas DataFrames with OHLCV data.
"""

from typing import Dict
import pandas as pd
import numpy as np
from data.fetcher import get_real_data


def strategy_moving_average_crossover(
    df: pd.DataFrame,
    params: Dict[str, int]
) -> pd.Series:
    """
    Generate trading signals based on moving average crossovers.
    
    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data with at least a 'close' column. Must be sorted by index.
    params : dict
        Strategy parameters:
        - 'fast_period': int, period for fast moving average (default: 10)
        - 'slow_period': int, period for slow moving average (default: 30)
    
    Returns
    -------
    pd.Series
        Signal series with values:
        - +1 for long (buy)
        - -1 for short (sell)
        - 0 for flat (no position)
    
    Examples
    --------
    >>> df = pd.DataFrame({'close': [100, 101, 102, 103, 104]})
    >>> params = {'fast_period': 2, 'slow_period': 3}
    >>> signals = strategy_moving_average_crossover(df, params)
    """
    # Extract parameters with defaults
    fast_period = params.get('fast_period', 10)
    slow_period = params.get('slow_period', 30)
    
    # Validate parameters
    if fast_period >= slow_period:
        raise ValueError("fast_period must be less than slow_period")
    if fast_period < 1 or slow_period < 1:
        raise ValueError("Periods must be positive integers")
    
    # Calculate moving averages (vectorized)
    fast_ma = df['close'].rolling(window=fast_period).mean()
    slow_ma = df['close'].rolling(window=slow_period).mean()
    
    # Initialize signal series with zeros
    signals = pd.Series(0, index=df.index)
    
    # Generate crossover signals using vectorized comparison
    # Fast MA crosses above Slow MA -> Long (+1)
    crossover_up = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
    signals.loc[crossover_up] = 1
    
    # Fast MA crosses below Slow MA -> Short (-1)
    crossover_down = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
    signals.loc[crossover_down] = -1
    
    # Handle NaN periods (no signal until both MAs are valid)
    signals = signals.fillna(0).astype(int)
    
    return signals


def generate_sample_data(n_periods: int = 500) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data for fallback when real data is unavailable.
    """
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.02, n_periods)
    close = 100 * np.exp(np.cumsum(returns))
    volatility = 0.01 * close
    high = close + np.abs(np.random.normal(0, volatility))
    low = close - np.abs(np.random.normal(0, volatility))
    open_price = close + np.random.normal(0, volatility * 0.5)
    volume = np.random.randint(1000, 10000, n_periods)
    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })
    return df


def main() -> None:
    """
    Demo runner for the moving average crossover strategy.
    
    Fetches real Oanda data (or cache) and runs the strategy.
    """
    print("=" * 60)
    print("Moving Average Crossover Strategy Demo")
    print("=" * 60)
    
    # Fetch real data (will use cache if available)
    print("\n1. Fetching market data (3 months EUR/USD H1)...")
    try:
        df = get_real_data(instrument="EUR_USD", granularity="H1", days=90, use_cache=True)
        print("   Source: Oanda (cached or live)")
    except Exception as e:
        print(f"   Real data fetch failed: {type(e).__name__}: {e}")
        df = generate_sample_data(n_periods=500)
    
    print(f"   Rows: {len(df)}")
    print(f"   Final close price: ${df['close'].iloc[-1]:.2f}")
    
    # Define strategy parameters
    params = {
        'fast_period': 10,
        'slow_period': 30
    }
    print(f"\n2. Strategy parameters:")
    print(f"   Fast MA period: {params['fast_period']}")
    print(f"   Slow MA period: {params['slow_period']}")
    
    # Generate signals
    print("\n3. Generating signals...")
    signals = strategy_moving_average_crossover(df, params)
    
    # Count signal types
    long_count = (signals == 1).sum()
    short_count = (signals == -1).sum()
    flat_count = (signals == 0).sum()
    
    print(f"   Long signals (+1):  {long_count}")
    print(f"   Short signals (-1): {short_count}")
    print(f"   Flat signals (0):   {flat_count}")
    
    # Show first few signals
    print("\n4. First 20 signals:")
    print(signals.head(20).to_string())
    
    # Basic performance metrics (directional accuracy)
    print("\n5. Directional accuracy check:")
    # Shift signals forward to see next period return direction
    next_returns = df['close'].pct_change().shift(-1).loc[signals != 0]
    signal_returns = signals.loc[signals != 0]
    
    # Count correct directional predictions
    correct = ((signal_returns > 0) & (next_returns > 0)) | ((signal_returns < 0) & (next_returns < 0))
    accuracy = correct.mean() if len(correct) > 0 else 0
    print(f"   Total non-zero signals: {len(signal_returns)}")
    print(f"   Directional accuracy: {accuracy:.2%}")
    
    print("\n" + "=" * 60)
    print("Strategy completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
