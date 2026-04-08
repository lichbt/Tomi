import pandas as pd
import numpy as np

def strategy_frama(close, high, low, volume, period=20, fc=1.0, sc=200.0):
    """
    Fractal Adaptive Moving Average (FRAMA) strategy with ATR trailing stops.

    Parameters:
    -----------
    close : pd.Series - Closing prices
    high : pd.Series - High prices
    low : pd.Series - Low prices
    volume : pd.Series - Volume data
    period : int - FRAMA calculation period (default 20)
    fc : float - Fast constant for fractal dimension scaling (default 1.0)
    sc : float - Slow constant for fractal dimension scaling (default 200.0)

    Returns:
    --------
    pd.Series - Trading signals:
                 1 = Long entry
                -1 = Short entry
                 0 = No position (flat or exit)
    """
    n = len(close)
    signals = pd.Series(0, index=close.index)

    if n < period * 2:
        return signals

    # Calculate ATR for trailing stops
    tr = pd.DataFrame()
    tr['h-l'] = high - low
    tr['h-pc'] = abs(high - close.shift(1))
    tr['l-pc'] = abs(low - close.shift(1))
    tr['tr'] = tr[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    atr = tr['tr'].rolling(window=14).mean()
    atr = atr.shift(1)  # Prevent lookahead

    # Calculate fractal dimension and smoothing constant (alpha)
    # FRAMA uses fractal dimension over two nested periods
    # D = (log(N1+N2) - log(N2)) / log(2) where N1 and N2 are ranges
    # alpha = exp(-4.6*(D-1))
    # Or simplified: alpha = (exp(-4.6*(D-1)) + 0.5) / 2

    # Calculate price changes for range calculation
    high_roll = high.rolling(window=period)
    low_roll = low.rolling(window=period)

    # N1: range over the entire period
    N1 = high_roll.max() - low_roll.min()

    # N2: range over half the period segments
    half_period = period // 2
    if half_period < 1:
        N2 = N1.copy()
    else:
        high_roll_half1 = high.rolling(window=half_period).max()
        low_roll_half1 = low.rolling(window=half_period).min()
        range1 = high_roll_half1 - low_roll_half1

        high_roll_half2 = high.shift(half_period).rolling(window=half_period).max()
        low_roll_half2 = low.shift(half_period).rolling(window=half_period).min()
        range2 = high_roll_half2 - low_roll_half2

        N2 = range1 + range2

    # Fractal dimension (D)
    D = (np.log10(N1 + N2) - np.log10(N2)) / np.log10(2)

    # Smoothing constant (alpha)
    old_alpha = 2 / (fc + 1)  # Fast limit
    alpha = (np.exp(-4.6 * (D - 1)) + old_alpha) / 2

    # Limit alpha between fast and slow constants
    new_alpha = np.clip(alpha, 2/(sc+1), 2/(fc+1))

    # Calculate FRAMA
    frama = close.copy()
    for i in range(period, n):
        if pd.isna(N1.iloc[i]) or pd.isna(N2.iloc[i]):
            frama.iloc[i] = close.iloc[i]
        else:
            a = new_alpha.iloc[i]
            if pd.isna(a):
                a = 2 / (fc + 1)
            frama.iloc[i] = a * close.iloc[i] + (1 - a) * frama.iloc[i-1]

    # Shift FRAMA by 1 to prevent lookahead bias in signals
    frama = frama.shift(1)

    # Generate signals based on price vs FRAMA crossovers
    # Use .shift(1) for previous values to avoid using current bar info
    price_above_frama = close > frama
    price_below_frama = close < frama

    # Entry signals
    bullish_crossover = (price_above_frama) & (~price_above_frama).shift(1)
    bearish_crossover = (price_below_frama) & (~price_below_frama).shift(1)

    # Initialize position tracking
    position = 0  # 0=flat, 1=long, -1=short
    atr_multiplier = 2.0

    for i in range(max(period, 14), n):
        # Skip if ATR is NaN
        if pd.isna(atr.iloc[i]) or pd.isna(frama.iloc[i]):
            continue

        current_close = close.iloc[i]
        current_atr = atr.iloc[i]

        # Long position logic
        if position == 1:
            # Check ATR trailing stop for long
            # For simplicity, use a trailing stop based on recent highs
            if i >= 1:
                # Entry price would be where we entered; track entry price separately
                pass  # Simplified: we'll use high prices against trailing stop
            # If bearish crossover occurs, exit long
            if bearish_crossover.iloc[i]:
                position = 0
                signals.iloc[i] = 0

        # Short position logic
        elif position == -1:
            # If bullish crossover occurs, exit short
            if bullish_crossover.iloc[i]:
                position = 0
                signals.iloc[i] = 0

        # Flat position - check for new entries
        else:
            if bullish_crossover.iloc[i]:
                position = 1
                signals.iloc[i] = 1
            elif bearish_crossover.iloc[i]:
                position = -1
                signals.iloc[i] = -1

    # Apply ATR-based trailing stops for exits
    # We need to track entry prices; let's re-run with tracking or add post-processing
    # Simpler approach: Use close against (entry_price ± N*ATR) to determine exits
    # We'll reconstruct positions and apply trailing stops

    signals = pd.Series(0, index=close.index)
    position = 0
    entry_price = None
    long_stop_price = None
    short_stop_price = None

    for i in range(max(period, 14), n):
        if pd.isna(atr.iloc[i]) or pd.isna(frama.iloc[i]):
            continue

        current_close = close.iloc[i]
        current_atr = atr.iloc[i]

        if position == 0:
            # Check for entry
            if bullish_crossover.iloc[i]:
                position = 1
                entry_price = current_close
                long_stop_price = entry_price - current_atr * atr_multiplier
                signals.iloc[i] = 1
            elif bearish_crossover.iloc[i]:
                position = -1
                entry_price = current_close
                short_stop_price = entry_price + current_atr * atr_multiplier
                signals.iloc[i] = -1

        elif position == 1:
            # Update trailing stop for long - only move up (raise stop)
            potential_new_stop = current_close - current_atr * atr_multiplier
            long_stop_price = max(long_stop_price, potential_new_stop)

            # Exit if price hits stop or bearish crossover
            if current_close <= long_stop_price:
                position = 0
                entry_price = None
                signals.iloc[i] = 0  # Exit signal (explicit 0 for exit)
            elif bearish_crossover.iloc[i]:
                position = 0
                entry_price = None
                signals.iloc[i] = 0

        elif position == -1:
            # Update trailing stop for short - only move down (lower stop)
            potential_new_stop = current_close + current_atr * atr_multiplier
            short_stop_price = min(short_stop_price, potential_new_stop)

            # Exit if price hits stop or bullish crossover
            if current_close >= short_stop_price:
                position = 0
                entry_price = None
                signals.iloc[i] = 0
            elif bullish_crossover.iloc[i]:
                position = 0
                entry_price = None
                signals.iloc[i] = 0

    return signals
