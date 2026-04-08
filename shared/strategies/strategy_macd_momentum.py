"""MACD Momentum with ADX Filter."""
import pandas as pd
import numpy as np


def strategy_macd_momentum(df: pd.DataFrame, params: dict) -> pd.Series:
    """MACD crossover with ADX trend strength filter."""
    macd_fast = params.get('macd_fast', 12)
    macd_slow = params.get('macd_slow', 26)
    macd_signal = params.get('macd_signal', 9)
    adx_period = params.get('adx_period', 14)
    adx_threshold = params.get('adx_threshold', 25)
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

    # MACD
    ema_fast = close.ewm(span=macd_fast).mean()
    ema_slow = close.ewm(span=macd_slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=macd_signal).mean()

    # ADX (simplified)
    tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
    plus_dm = (high - high.shift(1)).clip(lower=0)
    minus_dm = (low.shift(1) - low).clip(lower=0)
    atr_adx = tr.rolling(adx_period).mean()
    plus_di = 100 * (plus_dm.rolling(adx_period).mean() / (atr_adx + 1e-9))
    minus_di = 100 * (minus_dm.rolling(adx_period).mean() / (atr_adx + 1e-9))
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
    adx = dx.rolling(adx_period).mean()

    # ATR for stops
    atr = tr.rolling(atr_period).mean()

    # Signals
    signals = pd.Series(0.0, index=df.index)
    macd_cross_up = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
    macd_cross_down = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))
    trend_up = (adx > adx_threshold) & (plus_di > minus_di)
    trend_down = (adx > adx_threshold) & (minus_di > plus_di)

    position = 0
    entry_price = 0.0
    peak = 0.0
    trough = 0.0

    for i in range(max(macd_slow, adx_period), len(df)):
        if pd.isna(atr.iloc[i]) or atr.iloc[i] <= 0:
            signals.iloc[i] = position
            continue

        # Exit
        if position == 1:
            peak = max(peak, high.iloc[i])
            trail_stop = peak - stop_mult * atr.iloc[i]
            if risk_model == 'breakeven':
                profit = close.iloc[i] - entry_price
                if profit >= breakeven_atr * atr.iloc[i]:
                    trail_stop = max(trail_stop, entry_price + breakeven_buffer * atr.iloc[i])
            elif risk_model == 'percent_trail':
                profit = close.iloc[i] - entry_price
                if profit >= profit_switch_atr * atr.iloc[i]:
                    trail_stop = peak * (1 - percent_trail)
            if low.iloc[i] <= trail_stop:
                position = 0
        elif position == -1:
            trough = min(trough, low.iloc[i])
            trail_stop = trough + stop_mult * atr.iloc[i]
            if risk_model == 'breakeven':
                profit = entry_price - close.iloc[i]
                if profit >= breakeven_atr * atr.iloc[i]:
                    trail_stop = min(trail_stop, entry_price - breakeven_buffer * atr.iloc[i])
            elif risk_model == 'percent_trail':
                profit = entry_price - close.iloc[i]
                if profit >= profit_switch_atr * atr.iloc[i]:
                    trail_stop = trough * (1 + percent_trail)
            if high.iloc[i] >= trail_stop:
                position = 0

        # Entry
        if position == 0:
            if macd_cross_up.iloc[i] and trend_up.iloc[i]:
                position = 1
                entry_price = close.iloc[i]
                peak = high.iloc[i]
            elif macd_cross_down.iloc[i] and trend_down.iloc[i]:
                position = -1
                entry_price = close.iloc[i]
                trough = low.iloc[i]

        signals.iloc[i] = position

    return signals.astype(int)
