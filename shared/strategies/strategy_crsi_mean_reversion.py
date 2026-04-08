"""Connors RSI Mean Reversion.

Author: Strategy Coder Agent

ConnorsRSI (CRSI) = (RSI(2) + RSI_UpDown(5) + ROC Percentile Rank(100)) / 3

Entry Long:
  - CRSI < 5
  - Price breaks above 20-bar swing high

Entry Short:
  - CRSI > 95
  - Price breaks below 20-bar swing low

Exit:
  - CRSI reverts to 45-55 range (midpoint exit), OR
  - ATR trailing stop (default 2x ATR)
"""
from __future__ import annotations

import pandas as pd
import numpy as np


def _percentile_rank(series: pd.Series, period: int, min_periods: int = 1) -> pd.Series:
    """Rolling percentile rank of each value within a lookback window.

    For each bar *i*, compute the rank of ``series[i]`` relative to the
    preceding ``period`` values (inclusive of *i*).  Returns a float in
    [0, 100].
    """
    def _rank(x: np.ndarray) -> float:
        last = x[-1]
        count = len(x)
        return np.sum(x <= last) / count * 100.0

    return series.rolling(period, min_periods=min_periods).apply(
        _rank, raw=True
    )


def strategy_crsi_mean_reversion(df: pd.DataFrame, params: dict) -> pd.Series:
    """ConnorsRSI mean-reversion strategy with swing-breakout confirmation.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: ['open', 'high', 'low', 'close', 'volume'].
    params : dict
        - rsi_close_period : int, optional (default 2)
        - rsi_updown_period : int, optional (default 5)
        - roc_rank_period : int, optional (default 100)
        - swing_period : int, optional (default 20)
        - crsi_long_thresh : float, optional (default 10)
        - crsi_short_thresh : float, optional (default 90)
        - crsi_exit_low : float, optional (default 45)
        - crsi_exit_high : float, optional (default 55)
        - atr_period : int, optional (default 14)
        - stop_atr_mult : float, optional (default 2.0)

    Returns
    -------
    pd.Series
        Integer signals: 1 = long, -1 = short, 0 = flat.
        Shifted by 1 bar to prevent look-ahead bias.
    """
    # --- Extract columns ---------------------------------------------------------
    high = df['high'].astype(np.float64)
    low = df['low'].astype(np.float64)
    close = df['close'].astype(np.float64)

    # --- Strategy parameters -----------------------------------------------------
    rsi_close_period = params.get('rsi_close_period', 2)
    rsi_updown_period = params.get('rsi_updown_period', 5)
    roc_rank_period = params.get('roc_rank_period', 100)
    swing_period = params.get('swing_period', 20)
    crsi_long_thresh = params.get('crsi_long_thresh', 10)
    crsi_short_thresh = params.get('crsi_short_thresh', 90)
    crsi_exit_low = params.get('crsi_exit_low', 45)
    crsi_exit_high = params.get('crsi_exit_high', 55)
    atr_period = params.get('atr_period', 14)
    stop_atr_mult = params.get('stop_atr_mult', 2.0)

    # --- RSI(2) on close ---------------------------------------------------------
    def _rsi(source: pd.Series, period: int) -> pd.Series:
        delta = source.diff()
        gain = delta.where(delta > 0, 0.0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
        rs = gain / (loss + 1e-9)
        return 100.0 - (100.0 / (1.0 + rs))

    rsi_close = _rsi(close, rsi_close_period)

    # --- Up/Down streak RSI -------------------------------------------------------
    # Compute streak length: consecutive up or down days
    direction = close.diff()
    streak = np.where(direction > 0, 1, np.where(direction < 0, -1, 0))
    # Build running streak length
    streak_len = pd.Series(0.0, index=df.index, dtype=np.float64)
    for i in range(1, len(streak)):
        if streak[i] == streak[i - 1] and streak[i] != 0:
            streak_len.iloc[i] = streak_len.iloc[i - 1] + 1
        elif streak[i] != 0:
            streak_len.iloc[i] = 1
        else:
            streak_len.iloc[i] = 0
    rsi_updown = _rsi(streak_len, rsi_updown_period)

    # --- ROC Percentile Rank ------------------------------------------------------
    roc = close.pct_change(periods=1)
    roc_rank = _percentile_rank(roc, roc_rank_period)

    # --- ConnorsRSI ---------------------------------------------------------------
    crsi = (rsi_close + rsi_updown + roc_rank) / 3.0

    # --- Swing highs / lows (Donchian-style) --------------------------------------
    swing_high = high.rolling(swing_period).max()
    swing_low = low.rolling(swing_period).min()

    breakout_long = close > swing_high.shift(1)
    breakout_short = close < swing_low.shift(1)

    # --- ATR for trailing stop ----------------------------------------------------
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    # --- Signal generation loop ---------------------------------------------------
    signals = pd.Series(0, index=df.index)
    position = 0
    entry_price = 0.0
    peak = 0.0
    trough = 0.0

    lookback = max(rsi_close_period, rsi_updown_period, roc_rank_period,
                   swing_period, atr_period) + 5  # warm-up buffer

    for i in range(lookback, len(df)):
        if pd.isna(crsi.iloc[i]) or pd.isna(atr.iloc[i]) or atr.iloc[i] <= 0:
            signals.iloc[i] = position
            continue

        cur_high = high.iloc[i]
        cur_low = low.iloc[i]
        cur_close = close.iloc[i]
        cur_atr = atr.iloc[i]
        cur_crsi = crsi.iloc[i]

        # --- Exit logic ----------------------------------------------------------
        if position == 1:  # Long
            peak = max(peak, cur_high)
            stop_level = peak - stop_atr_mult * cur_atr
            # CRSI mean reversion exit or ATR stop
            if cur_crsi >= crsi_exit_low or cur_low <= stop_level:
                position = 0
        elif position == -1:  # Short
            trough = min(trough, cur_low)
            stop_level = trough + stop_atr_mult * cur_atr
            if cur_crsi <= crsi_exit_high or cur_high >= stop_level:
                position = 0

        # --- Entry logic (only when flat) -----------------------------------------
        if position == 0:
            if cur_crsi < crsi_long_thresh and breakout_long.iloc[i]:
                position = 1
                entry_price = cur_close
                peak = cur_high
            elif cur_crsi > crsi_short_thresh and breakout_short.iloc[i]:
                position = -1
                entry_price = cur_close
                trough = cur_low

        signals.iloc[i] = position

    # --- Prevent look-ahead bias ---------------------------------------------------
    return signals.astype(int).shift(1).fillna(0).astype(int)
