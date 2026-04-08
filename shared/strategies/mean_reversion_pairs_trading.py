"""
Mean Reversion Pairs Trading (ICICI vs HDFC)

Source: https://github.com/Vipluv01/icici_mean_reversion
Indicators: Z-score (5-day rolling), Kalman Filter (dynamic hedge ratio)
"""

import pandas as pd
import numpy as np
from pykalman import KalmanFilter

def strategy_meanreversionpairs(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """
    Pairs trading between ICICI and HDFC using Kalman Filter hedge ratio
    and Z-score mean reversion.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns for both instruments: 'ICICI' and 'HDFC' (or 'close_ICICI', 'close_HDFC')
        Or, for single-instrument mode, use spread precomputed as 'spread'
    params : dict, optional
        'window' : rolling window for z-score (default 5)
        'entry_threshold' : z-score threshold for entry (default 1.5)
        'exit_threshold' : z-score threshold for exit (default 0.1)
        'stop_threshold' : z-score stop loss (default 3.0)

    Returns
    -------
    pd.Series
        Signals: +1 (long spread), -1 (short spread), 0 (flat)
    """
    # Default params
    p = params or {}
    window = p.get('window', 5)
    entry_th = p.get('entry_threshold', 1.5)
    exit_th = p.get('exit_threshold', 0.1)
    stop_th = p.get('stop_threshold', 3.0)

    # Get price series
    if 'ICICI' in df.columns and 'HDFC' in df.columns:
        price_a = df['ICICI']
        price_b = df['HDFC']
    elif 'close_ICICI' in df.columns and 'close_HDFC' in df.columns:
        price_a = df['close_ICICI']
        price_b = df['close_HDFC']
    else:
        raise ValueError("DataFrame must contain ICICI and HDFC price columns")

    # Kalman Filter to get dynamic hedge ratio
    kf = KalmanFilter(
        transition_matrices=[1],
        observation_matrices=np.ones((1, 1)),
        initial_state_mean=price_a.iloc[0] / price_b.iloc[0],
        initial_state_covariance=1,
        observation_covariance=1,
        transition_covariance=0.01
    )
    hedge_ratio, _ = kf.filter(price_a.values / price_b.values)
    hedge_ratio = pd.Series(hedge_ratio.flatten(), index=df.index)

    spread = price_a - hedge_ratio * price_b

    # Rolling statistics
    rolling_mean = spread.rolling(window).mean()
    rolling_std = spread.rolling(window).std()
    zscore = (spread - rolling_mean) / rolling_std

    # Signals
    signals = pd.Series(0, index=df.index)
    signals[zscore < -entry_th] = 1   # Long spread
    signals[zscore > entry_th] = -1  # Short spread
    signals[abs(zscore) < exit_th] = 0  # Exit

    # Stop loss
    stop_mask = abs(zscore) > stop_th
    signals[stop_mask] = 0

    return signals