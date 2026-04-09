"""
Strategy 8: Kalman Filter Mean Reversion
Status: 🧪 Ready for Backtesting
Source: https://www.quantifiedstrategies.com/kalman-filter-trading-strategy/
"""

import pandas as pd
import numpy as np


def _kalman_filter(close: np.ndarray, transition_cov: float = 0.01, obs_cov: float = 1.0) -> np.ndarray:
    """Simple 1D Kalman Filter implementation."""
    n = len(close)
    state = np.zeros(n)
    P = np.zeros(n)
    
    # Initialize
    state[0] = close[0]
    P[0] = 1.0
    
    for t in range(1, n):
        # Prediction
        state_pred = state[t-1]
        P_pred = P[t-1] + transition_cov
        
        # Update
        K = P_pred / (P_pred + obs_cov)  # Kalman gain
        state[t] = state_pred + K * (close[t] - state_pred)
        P[t] = (1 - K) * P_pred
    
    return state


def strategy_kalman_mean_reversion(
    df: pd.DataFrame,
    lookback_short: int = 5,
    transition_cov: float = 0.01,
    obs_cov: float = 1.0,
    adx_threshold: float = 25.0
) -> pd.Series:
    """
    Kalman Filter Mean Reversion strategy.
    
    Entry Long: 5-day SMA crosses below Kalman Filter (price below fair value)
    Entry Short: 5-day SMA crosses above Kalman Filter (price above fair value)
    Exit: Opposite crossover
    
    Args:
        df: DataFrame with 'close', 'high', 'low' columns
        lookback_short: Period for short-term SMA
        transition_cov: Kalman filter transition covariance
        obs_cov: Kalman filter observation covariance
        adx_threshold: Optional ADX filter for trending markets
    
    Returns:
        pd.Series with signals: 1 (long), -1 (short), 0 (flat)
    """
    df = df.copy()
    
    close = df['close'].values
    
    # Compute Kalman Filter state estimate
    df['kalman'] = _kalman_filter(close, transition_cov, obs_cov)
    
    # Short-term SMA
    df['sma_short'] = df['close'].rolling(lookback_short).mean()
    
    # Optional ADX filter (if column exists)
    if 'adx' in df.columns:
        df['trend_filter'] = df['adx'] > adx_threshold
    else:
        df['trend_filter'] = True  # No filter if ADX not available
    
    # Signal generation with shift(1) to avoid lookahead
    df['kalman_lag'] = df['kalman'].shift(1)
    df['sma_short_lag'] = df['sma_short'].shift(1)
    df['sma_short_prev'] = df['sma_short'].shift(2)
    df['kalman_prev'] = df['kalman'].shift(2)
    
    df['signal_raw'] = 0
    
    # Long entry: SMA crosses below Kalman (was above, now below)
    long_entry = (
        (df['sma_short_prev'] >= df['kalman_prev']) & 
        (df['sma_short_lag'] < df['kalman_lag']) &
        df['trend_filter'].shift(1)
    )
    df.loc[long_entry, 'signal_raw'] = 1
    
    # Short entry: SMA crosses above Kalman (was below, now above)
    short_entry = (
        (df['sma_short_prev'] <= df['kalman_prev']) & 
        (df['sma_short_lag'] > df['kalman_lag']) &
        df['trend_filter'].shift(1)
    )
    df.loc[short_entry, 'signal_raw'] = -1
    
    # Exit: opposite crossover
    df['position'] = df['signal_raw'].replace(0, np.nan).ffill().fillna(0)
    
    # Exit when signal reverses
    df.loc[df['position'] == 1, 'exit_long'] = (
        (df['sma_short_prev'] <= df['kalman_prev']) & 
        (df['sma_short_lag'] > df['kalman_lag'])
    )
    df.loc[df['position'] == -1, 'exit_short'] = (
        (df['sma_short_prev'] >= df['kalman_prev']) & 
        (df['sma_short_lag'] < df['kalman_lag'])
    )
    
    df.loc[df['exit_long'] | df['exit_short'], 'position'] = 0
    
    return df['position'].shift(1).fillna(0).astype(int)
