"""
Strategy 9: RSI(2) Connors Mean Reversion
Status: 🧪 Ready for Backtesting
Source: Larry Connors & Cesar Alvarez — "Short Term Trading Strategies That Work" (2008)
URL: https://www.quantifiedstrategies.com/rsi-2-strategy/
"""

import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator


def strategy_rsi2_connors(
    df: pd.DataFrame,
    sma_long_period: int = 200,
    rsi_period: int = 2,
    rsi_entry_long: float = 5,
    rsi_entry_short: float = 95,
    rsi_exit_long: float = 65,
    rsi_exit_short: float = 30,
    sma_exit_period: int = 5
) -> pd.Series:
    """
    RSI(2) Connors Mean Reversion strategy.
    
    Trend Filter (daily): 
        - Long: Close > 200-day SMA
        - Short: Close < 200-day SMA
    Entry Trigger:
        - Long: RSI(2) < 5
        - Short: RSI(2) > 95
    Exit Rules:
        - Long: RSI(2) > 65 OR Close > 5-day SMA
        - Short: RSI(2) < 30 OR Close < 5-day SMA
    
    Args:
        df: DataFrame with 'close' column
        sma_long_period: Long-term SMA period for trend filter
        rsi_period: RSI period (2 for hyper-sensitive)
        rsi_entry_long: RSI threshold for long entry
        rsi_entry_short: RSI threshold for short entry
        rsi_exit_long: RSI threshold for long exit
        rsi_exit_short: RSI threshold for short exit
        sma_exit_period: SMA period for exit confirmation
    
    Returns:
        pd.Series with signals: 1 (long), -1 (short), 0 (flat)
    """
    df = df.copy()
    
    # Compute indicators
    df['sma_long'] = df['close'].rolling(sma_long_period).mean()
    df['sma_exit'] = df['close'].rolling(sma_exit_period).mean()
    df['rsi_2'] = RSIIndicator(df['close'], window=rsi_period).rsi()
    
    # Lag to avoid lookahead
    df['close_lag'] = df['close'].shift(1)
    df['sma_long_lag'] = df['sma_long'].shift(1)
    df['sma_exit_lag'] = df['sma_exit'].shift(1)
    df['rsi_2_lag'] = df['rsi_2'].shift(1)
    df['rsi_2_prev'] = df['rsi_2'].shift(2)
    
    # Trend direction (lagged)
    df['above_sma_long'] = df['close_lag'] > df['sma_long_lag']
    df['below_sma_long'] = df['close_lag'] < df['sma_long_lag']
    
    # Signal generation
    df['signal'] = 0
    
    # Long entry: above SMA(200) AND RSI(2) crosses below 5
    long_entry = (
        df['above_sma_long'] & 
        (df['rsi_2_prev'] >= rsi_entry_long) & 
        (df['rsi_2_lag'] < rsi_entry_long)
    )
    df.loc[long_entry, 'signal'] = 1
    
    # Short entry: below SMA(200) AND RSI(2) crosses above 95
    short_entry = (
        df['below_sma_long'] & 
        (df['rsi_2_prev'] <= rsi_entry_short) & 
        (df['rsi_2_lag'] > rsi_entry_short)
    )
    df.loc[short_entry, 'signal'] = -1
    
    # Maintain position until exit
    df['position'] = df['signal'].replace(0, np.nan).ffill().fillna(0)
    
    # Long exit: RSI(2) > 65 OR Close > SMA(5)
    df.loc[
        (df['position'] == 1) & 
        ((df['rsi_2_lag'] > rsi_exit_long) | (df['close_lag'] > df['sma_exit_lag'])),
        'position'
    ] = 0
    
    # Short exit: RSI(2) < 30 OR Close < SMA(5)
    df.loc[
        (df['position'] == -1) & 
        ((df['rsi_2_lag'] < rsi_exit_short) | (df['close_lag'] < df['sma_exit_lag'])),
        'position'
    ] = 0
    
    return df['position'].shift(1).fillna(0).astype(int)
