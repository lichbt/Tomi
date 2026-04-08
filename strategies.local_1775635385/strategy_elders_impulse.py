"""Elder's Impulse System Strategy.

A trend-following + momentum strategy combining EMA slope direction
with MACD histogram momentum to generate impulse signals.

Parameters
----------
close : pd.Series — Close prices (OHLCV)
high : pd.Series — High prices (OHLCV)
low : pd.Series — Low prices (OHLCV)
volume : pd.Series — Volume (OHLCV)
ema_period : int — EMA period for trend filter (default 13)
macd_fast : int — Fast EMA span for MACD (default 12)
macd_slow : int — Slow EMA span for MACD (default 26)
macd_signal : int — Signal line span for MACD (default 9)

Returns
-------
pd.Series — Signal series with values:
    1  = LONG entry / hold
   -1  = SHORT entry / hold
    0  = FLAT / exit

Strategy Logic
--------------
1. Trend Filter (EMA slope):
   - Bullish  when EMA[i] > EMA[i-1]  (slope up)
   - Bearish  when EMA[i] < EMA[i-1]  (slope down)

2. Momentum Filter (MACD Histogram direction):
   - Bullish  when histogram[i] > histogram[i-1]  (rising)
   - Bearish  when histogram[i] < histogram[i-1]  (falling)

3. Entry Signals (both filters must agree):
   - LONG  =  EMA UP  AND  histogram RISING
   - SHORT =  EMA DOWN AND histogram FALLING
   - FLAT  =  mixed signals -> wait

4. Exit Signals:
   - Exit LONG  when histogram falls OR EMA slope reverses down
   - Exit SHORT when histogram rises OR EMA slope reverses up
   - ATR(14) trailing stop:
     LONG  exit if close < entry_price - 2.5 * entry_ATR
     SHORT exit if close > entry_price + 2.5 * entry_ATR

5. All indicator comparisons use .shift(1) to prevent lookahead bias.
"""

import pandas as pd
import numpy as np


def strategy_elders_impulse(
    close,
    high,
    low,
    volume,
    ema_period=13,
    macd_fast=12,
    macd_slow=26,
    macd_signal=9,
):
    """Generate Elder's Impulse System signals.

    See module docstring for full strategy description.
    """
    n = len(close)
    min_bars = max(ema_period, macd_slow) + macd_signal + 2  # ~52
    if n < min_bars:
        return pd.Series(0, index=close.index)

    # ---- Indicators (no lookahead: compare vs. shift(1)) ----

    # EMA trend line
    ema = close.ewm(span=ema_period, adjust=False).mean()
    ema_prev = ema.shift(1)

    # MACD from scratch (pure pandas)
    ema_fast = close.ewm(span=macd_fast, adjust=False).mean()
    ema_slow = close.ewm(span=macd_slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=macd_signal, adjust=False).mean()
    histogram = macd_line - signal_line
    hist_prev = histogram.shift(1)

    # ATR(14) for trailing stop
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(span=14, adjust=False).mean()

    # ---- Boolean filters using shift(1) to avoid lookahead ----
    ema_up = ema > ema_prev      # trend bullish
    ema_down = ema < ema_prev    # trend bearish
    hist_rising = histogram > hist_prev   # momentum rising
    hist_falling = histogram < hist_prev  # momentum falling

    # Combined impulse (both filters agree)
    impulse_long = ema_up & hist_rising
    impulse_short = ema_down & hist_falling

    # Exit conditions (either filter turns against the position)
    exit_long = hist_falling | ema_down
    exit_short = hist_rising | ema_up

    # ---- Explicit position tracking loop ----
    signals = np.zeros(n, dtype=int)
    position = 0          # 0 = flat, 1 = long, -1 = short
    entry_price = 0.0
    entry_atr = 0.0
    long_stop_price = 0.0
    short_stop_price = 0.0

    values_array = close.values
    atr_array = atr.values
    impulse_long_arr = impulse_long.values
    impulse_short_arr = impulse_short.values
    exit_long_arr = exit_long.values
    exit_short_arr = exit_short.values

    for i in range(n):
        # Skip bars where key indicators are NaN
        if np.isnan(values_array[i]) or np.isnan(atr_array[i]):
            signals[i] = 0
            continue

        price = values_array[i]
        current_atr = atr_array[i]

        # Check trailing stop exits first (secondary exit)
        if position == 1 and long_stop_price > 0:
            if price < long_stop_price:
                position = 0
                entry_price = 0.0
                long_stop_price = 0.0
                signals[i] = 0
                continue

        if position == -1 and short_stop_price > 0:
            if price > short_stop_price:
                position = 0
                entry_price = 0.0
                short_stop_price = 0.0
                signals[i] = 0
                continue

        # --- In a LONG position ---
        if position == 1:
            if exit_long_arr[i]:
                position = 0
                entry_price = 0.0
                long_stop_price = 0.0
                signals[i] = 0
            else:
                signals[i] = 1
            continue

        # --- In a SHORT position ---
        if position == -1:
            if exit_short_arr[i]:
                position = 0
                entry_price = 0.0
                short_stop_price = 0.0
                signals[i] = 0
            else:
                signals[i] = -1
            continue

        # --- FLAT, looking for entry ---
        if impulse_long_arr[i]:
            position = 1
            entry_price = price
            entry_atr = current_atr if not np.isnan(current_atr) else 0.0
            long_stop_price = entry_price - 2.5 * entry_atr
            signals[i] = 1

        elif impulse_short_arr[i]:
            position = -1
            entry_price = price
            entry_atr = current_atr if not np.isnan(current_atr) else 0.0
            short_stop_price = entry_price + 2.5 * entry_atr
            signals[i] = -1

        else:
            signals[i] = 0

    return pd.Series(signals, index=close.index, name="elders_impulse")
