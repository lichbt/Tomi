"""
Donchian Channel Breakout Strategy with ATR Trailing Stop.

Entry: Breakout above/below previous Donchian channel with SMA trend filter.
Exit: ATR-based trailing stop from highest/lowest since entry.
"""

import pandas as pd
import numpy as np


def strategy_donchian_breakout(
    df: pd.DataFrame,
    params: dict
) -> pd.Series:
    """
    Donchian Channel Breakout with trend filter and ATR trailing stop.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data with columns: open, high, low, close, volume
    params : dict
        'donch_period': int (default 20) - Donchian channel lookback
        'sma_filter': int (default 200) - SMA trend filter period
        'atr_period': int (default 14) - ATR calculation period
        'stop_atr_mult': float (default 2.0) - ATR multiplier for trailing stop

    Returns
    -------
    pd.Series : +1 (long), -1 (short), 0 (flat)
    """
    donch_window = params.get('donch_period', 20)
    sma_filter = params.get('sma_filter', 200)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_atr_mult', 2.0)
    risk_model = params.get('risk_model', 'baseline')
    if risk_model == 'breakeven':
        breakeven_atr = params.get('breakeven_atr', 2.0)
        breakeven_buffer = params.get('breakeven_buffer', 0.5)
    elif risk_model == 'percent_trail':
        profit_switch_atr = params.get('profit_switch_atr', 4.0)
        percent_trail = params.get('percent_trail', 0.02)

    close = df['close']
    high = df['high']
    low = df['low']

    # Donchian channels
    donch_high = high.rolling(donch_window).max()
    donch_low = low.rolling(donch_window).min()

    # SMA trend filter
    sma = close.rolling(sma_filter).mean()

    # ATR
    tr = pd.concat([
        high - low,
        abs(high - close.shift(1)),
        abs(low - close.shift(1))
    ], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    # Previous channel values
    prev_high = donch_high.shift(1)
    prev_low = donch_low.shift(1)

    # Breakout conditions
    long_break = (close > prev_high) & (close > sma)
    short_break = (close < prev_low) & (close < sma)

    # Initialize signals
    signals = pd.Series(0.0, index=df.index)

    # State tracking
    position = 0  # 0=flat, 1=long, -1=short
    entry_price = 0.0
    peak_price = 0.0  # for long trailing
    trough_price = 0.0  # for short trailing

    for i in range(sma_filter, len(df)):
        current_close = close.iloc[i]
        current_high = high.iloc[i]
        current_low = low.iloc[i]
        current_atr = atr.iloc[i]

        if pd.isna(current_atr) or current_atr <= 0:
            signals.iloc[i] = position
            continue

        # --- Exit Logic ---
        if position == 1:  # Long
            peak_price = max(peak_price, current_high)
            trail_stop = peak_price - stop_mult * current_atr
            # Apply risk model adjustments
            if risk_model == 'breakeven':
                profit = current_close - entry_price
                if profit >= breakeven_atr * current_atr:
                    trail_stop = max(trail_stop, entry_price + breakeven_buffer * current_atr)
            elif risk_model == 'percent_trail':
                profit = current_close - entry_price
                if profit >= profit_switch_atr * current_atr:
                    trail_stop = peak_price * (1 - percent_trail)
            if current_low <= trail_stop:
                position = 0

        elif position == -1:  # Short
            trough_price = min(trough_price, current_low)
            trail_stop = trough_price + stop_mult * current_atr
            if risk_model == 'breakeven':
                profit = entry_price - current_close
                if profit >= breakeven_atr * current_atr:
                    trail_stop = min(trail_stop, entry_price - breakeven_buffer * current_atr)
            elif risk_model == 'percent_trail':
                profit = entry_price - current_close
                if profit >= profit_switch_atr * current_atr:
                    trail_stop = trough_price * (1 + percent_trail)
            if current_high >= trail_stop:
                position = 0

        # --- Entry Logic ---
        if position == 0:
            if long_break.iloc[i]:
                position = 1
                entry_price = current_close
                peak_price = current_high
            elif short_break.iloc[i]:
                position = -1
                entry_price = current_close
                trough_price = current_low

        signals.iloc[i] = position

    return signals.astype(int)


def main():
    """Quick test."""
    from data.fetcher import get_real_data
    print("Fetching EUR/USD H4 data...")
    df = get_real_data("EUR_USD", "H4", days=365)
    print(f"Loaded {len(df)} bars")

    params = {
        'donch_period': 20,
        'sma_filter': 200,
        'atr_period': 14,
        'stop_atr_mult': 2.0
    }
    signals = strategy_donchian_breakout(df, params)
    print(f"Signals: {(signals != 0).sum()} ({(signals == 1).sum()} long, {(signals == -1).sum()} short)")


if __name__ == "__main__":
    main()
