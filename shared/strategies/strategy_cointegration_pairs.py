"""
Strategy 6: Classic Cointegration Pairs Trading (WTI/Brent Crude)
Status: 🧪 Ready for Backtesting
Source: https://databento.com/blog/build-a-pairs-trading-strategy-in-python
"""

import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import coint


def strategy_cointegration_pairs(
    df: pd.DataFrame,
    x_col: str = 'x',
    y_col: str = 'y',
    lookback: int = 100,
    entry_threshold: float = 1.5,
    exit_threshold: float = 0.5,
    p_threshold: float = 0.05
) -> pd.Series:
    """
    Cointegration-based pairs trading strategy.
    
    Entry Long: z < -ENTRY_THRESHOLD (buy Y, sell X)
    Entry Short: z > ENTRY_THRESHOLD (sell Y, buy X)
    Exit: |z| < EXIT_THRESHOLD
    
    Args:
        df: DataFrame with x_col and y_col price columns
        x_col: Column name for asset X (e.g., 'WTI')
        y_col: Column name for asset Y (e.g., 'Brent')
        lookback: Rolling window size for cointegration
        entry_threshold: Z-score threshold for entry
        exit_threshold: Z-score threshold for exit
    
    Returns:
        pd.Series with signals: 1 (long Y, short X), -1 (short Y, long X), 0 (flat)
    """
    df = df.copy()
    
    # Initialize columns
    df['cointegrated'] = 0
    df['residual'] = 0.0
    df['zscore'] = 0.0
    df['position'] = 0
    
    is_cointegrated = False
    hedge_ratio = 1.0
    intercept = 0.0
    
    # Rolling window approach
    for i in range(lookback, len(df)):
        if i % lookback != 0:
            continue
            
        # Extract lookback window
        x = df[x_col].iloc[i-lookback:i].values
        y = df[y_col].iloc[i-lookback:i].values
        
        # Check for cointegration
        try:
            _, p_value, _ = coint(y, x)
            is_cointegrated = p_value < p_threshold
        except:
            is_cointegrated = False
        
        if is_cointegrated:
            # Update hedge ratio using OLS
            x_mean = np.mean(x)
            y_mean = np.mean(y)
            covariance = np.mean((x - x_mean) * (y - y_mean))
            x_var = np.mean((x - x_mean) ** 2)
            if x_var > 0:
                hedge_ratio = covariance / x_var
                intercept = y_mean - hedge_ratio * x_mean
            
            # Compute residuals for lookback period
            residuals = y - hedge_ratio * x - intercept
            
            # Compute z-score parameters
            residual_mean = np.mean(residuals)
            residual_std = np.std(residuals)
            
            if residual_std > 0:
                # Forward window: compute z-score
                x_forward = df[x_col].iloc[i:i+lookback].values
                y_forward = df[y_col].iloc[i:i+lookback].values
                
                spread_forward = y_forward - hedge_ratio * x_forward - intercept
                zscore_forward = (spread_forward - residual_mean) / residual_std
                
                # Assign to df
                end_idx = min(i + lookback, len(df))
                df.iloc[i:end_idx, df.columns.get_loc('zscore')] = zscore_forward[:end_idx-i]
                df.iloc[i:end_idx, df.columns.get_loc('cointegrated')] = 1
    
    # Generate trading signals using shift(1) to avoid lookahead
    df['zscore_lag'] = df['zscore'].shift(1)
    
    # Entry signals
    df.loc[df['zscore_lag'] < -entry_threshold, 'position'] = 1   # Long Y, Short X
    df.loc[df['zscore_lag'] > entry_threshold, 'position'] = -1  # Short Y, Long X
    
    # Exit signals - flat when z-score reverts
    df.loc[abs(df['zscore_lag']) < exit_threshold, 'position'] = 0
    
    # Prevent double entry - maintain position until exit
    df['position'] = df['position'].replace(0, np.nan).ffill().fillna(0)
    
    return df['position'].shift(1).fillna(0).astype(int)
