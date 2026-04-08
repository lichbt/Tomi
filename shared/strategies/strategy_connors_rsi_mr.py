# Strategy: Connors RSI Mean Reversion
# Author: Strategy Coder Agent
# Edge: Multi-factor mean reversion (RSI3 + streak length + ROC percentile)
# Libraries: pandas, numpy only

import pandas as pd
import numpy as np
from typing import Dict


def strategy_connors_rsi_mr(
    df: pd.DataFrame,
    params: Dict[str, any]
) -> pd.Series:
    """
    Connors RSI Mean Reversion strategy (position-holding mode).

    Connors RSI = (RSI(close,3) + RSI(streak,2) + PercentRank(ROC,100)) / 3

    Entry Long:  CRSI < entry_threshold
    Entry Short: CRSI > 100 - entry_threshold
    Exit Long:   CRSI > exit_threshold OR ATR trailing stop
    Exit Short:  CRSI < 100 - exit_threshold OR ATR trailing stop

    Args:
        df: OHLCV DataFrame
        params: {
            'rsi_period': int (default 3),
            'streak_rsi': int (default 2),
            'roc_period': int (default 100),
            'entry_threshold': float (default 15),
            'exit_threshold': float (default 65),
            'atr_period': int (default 14),
            'stop_atr_mult': float (default 3.0),
        }

    Returns:
        pd.Series: +1 (long), -1 (short), 0 (flat)
    """
    required = {'open', 'high', 'low', 'close', 'volume'}
    if not required.issubset(df.columns):
        raise ValueError(f'Missing columns: {required - set(df.columns)}')

    rsi_period = params.get('rsi_period', 3)
    streak_rsi = params.get('streak_rsi', 2)
    roc_period = params.get('roc_period', 100)
    entry_thresh = params.get('entry_threshold', 15)
    exit_thresh = params.get('exit_threshold', 65)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 3.0)

    close = df['close']

    # RSI(3)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(rsi_period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(rsi_period).mean()
    rs = gain / (loss + 1e-9)
    rsi_short = 100 - (100 / (1 + rs))

    # Streak RSI (vectorized)
    direction = np.sign(close.diff())
    streak = np.zeros(len(close))
    for i in range(1, len(close)):
        if direction.iloc[i] > 0:
            streak[i] = streak[i - 1] + 1 if streak[i - 1] >= 0 else 1
        elif direction.iloc[i] < 0:
            streak[i] = streak[i - 1] - 1 if streak[i - 1] <= 0 else -1
    streak_s = pd.Series(streak, index=close.index)
    s_gain = streak_s.where(streak_s > 0, 0.0).rolling(streak_rsi).mean()
    s_loss = (-streak_s).where(streak_s < 0, 0.0).rolling(streak_rsi).mean()
    streak_rs = s_gain / (s_loss + 1e-9)
    rsi_streak = 100 - (100 / (1 + streak_rs))

    # ROC Percentile Rank (using z-score approximation for speed)
    roc = close.pct_change(1)
    r_mean = roc.rolling(roc_period).mean()
    r_std = roc.rolling(roc_period).std()
    z = (roc - r_mean) / (r_std + 1e-9)
    percent_rank = 50 + 50 * z.clip(-1, 1)

    crsi = (rsi_short + rsi_streak + percent_rank) / 3

    # ATR
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - close.shift(1)).abs(),
        (df['low'] - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    # Position-holding
    signals = pd.Series(0, index=df.index)
    position = 0
    peak = 0.0
    trough = 0.0

    start_i = max(rsi_period, streak_rsi, roc_period, atr_period)
    for i in range(start_i, len(df)):
        if np.isnan(crsi.iloc[i]) or np.isnan(atr.iloc[i]):
            continue

        if position == 1:
            peak = max(peak, df['high'].iloc[i])
            if crsi.iloc[i] > exit_thresh or df['low'].iloc[i] <= peak - atr.iloc[i] * stop_mult:
                position = 0
            elif crsi.iloc[i] > (100 - entry_thresh):
                position = -1
                trough = df['low'].iloc[i]
        elif position == -1:
            trough = min(trough, df['low'].iloc[i])
            if crsi.iloc[i] < (100 - exit_thresh) or df['high'].iloc[i] >= trough + atr.iloc[i] * stop_mult:
                position = 0
            elif crsi.iloc[i] < entry_thresh:
                position = 1
                peak = df['high'].iloc[i]
        else:
            if crsi.iloc[i] < entry_thresh:
                position = 1
                peak = df['high'].iloc[i]
            elif crsi.iloc[i] > (100 - entry_thresh):
                position = -1
                trough = df['low'].iloc[i]

        signals.iloc[i] = position

    signals = signals.shift(1).fillna(0).astype(int)
    return signals
