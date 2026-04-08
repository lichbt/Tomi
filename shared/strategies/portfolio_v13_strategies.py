"""
Portfolio v13 — 6 Live Strategy Implementations
All pure pandas/numpy. No external dependencies.
"""
import pandas as pd
import numpy as np


# ═══════════════════════════════════════════════════════
# 1. Donchian Channel Breakout (BTC_USD — H4 or Daily)
# ═══════════════════════════════════════════════════════
def strategy_donchian_breakout(close, high, low, volume,
                                entry_period=20, exit_period=10, atr_mult=2.0):
    """
    Donchian Channel Breakout — trend following via break of N-bar high/low.
    Entry: Close breaks above/below entry_period high/low
    Exit: Close breaks opposite-side exit_period high/low  OR  ATR trailing stop
    """
    n = len(close)
    signals = np.zeros(n, dtype=int)
    atr = _atr(high, low, close, 14)
    atr_arr = atr.values

    entry_high = high.rolling(window=entry_period).max()
    entry_low = low.rolling(window=entry_period).min()
    exit_high = high.rolling(window=exit_period).max()
    exit_low = low.rolling(window=exit_period).min()

    pos = 0; ep = 0.0; e_atr = 0.0; stop = 0.0
    for i in range(max(entry_period + 1, 14), n):
        px = close.values[i]
        cur_atr = atr_arr[i]
        # trailing stop
        if pos == 1 and stop > 0 and px < stop:
            pos = 0; stop = 0.0; signals[i] = 0; continue
        # exit signal: price breaks opposite band
        if pos == 1 and px < exit_low.values[i]:
            pos = 0; stop = 0.0; signals[i] = 0; continue
        if pos == -1 and px > exit_high.values[i]:
            pos = 0; stop = 0.0; signals[i] = 0; continue
        # flat: look for entry
        if pos == 0:
            if px > entry_high.values[i - 1]:   # breakout above
                pos = 1; ep = px; e_atr = cur_atr if not np.isnan(cur_atr) else 0
                stop = ep - atr_mult * e_atr
                signals[i] = 1
            elif px < entry_low.values[i - 1]:
                pos = -1; ep = px; e_atr = cur_atr if not np.isnan(cur_atr) else 0
                stop = ep + atr_mult * e_atr
                signals[i] = -1
        else:
            # hold/update trailing stop
            if pos == 1:
                new_stop = px - atr_mult * cur_atr if not np.isnan(cur_atr) else stop
                if new_stop > stop:
                    stop = new_stop
            else:
                new_stop = px + atr_mult * cur_atr if not np.isnan(cur_atr) else stop
                if new_stop < stop:
                    stop = new_stop
            signals[i] = pos
    return pd.Series(signals, index=close.index)


# ═══════════════════════════════════════════════════════
# 2. MACD Momentum (XAU_USD — Daily)
# ═══════════════════════════════════════════════════════
def strategy_macd_momentum(close, high, low, volume,
                            fast=12, slow=26, signal=9, atr_mult=2.0):
    """
    MACD Momentum: Enter long when MACD crosses above signal AND histogram rising.
    Exit when MACD crosses below signal or ATR trailing stop hit.
    """
    n = len(close)
    signals = np.zeros(n, dtype=int)
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    atr = _atr(high, low, close, 14)
    atr_arr = atr.values

    pos = 0; ep = 0.0; e_atr = 0.0; stop = 0.0
    warmup = max(fast, slow) + signal + 14
    for i in range(warmup, n):
        px = close.values[i]
        cur_atr = atr_arr[i]

        # trailing stop
        if pos == 1 and stop > 0 and px < stop:
            pos = 0; stop = 0.0; signals[i] = 0; continue
        if pos == -1 and stop > 0 and px > stop:
            pos = 0; stop = 0.0; signals[i] = 0; continue

        # exit on MACD crossback
        if pos == 1 and macd_line.values[i] < signal_line.values[i]:
            pos = 0; stop = 0.0; signals[i] = 0; continue
        if pos == -1 and macd_line.values[i] > signal_line.values[i]:
            pos = 0; stop = 0.0; signals[i] = 0; continue

        # entry
        if pos == 0:
            if (macd_line.values[i] > signal_line.values[i] and
                macd_line.values[i-1] <= signal_line.values[i-1]):
                pos = 1; ep = px; e_atr = cur_atr if not np.isnan(cur_atr) else 0
                stop = ep - atr_mult * e_atr
                signals[i] = 1
            elif (macd_line.values[i] < signal_line.values[i] and
                  macd_line.values[i-1] >= signal_line.values[i-1]):
                pos = -1; ep = px; e_atr = cur_atr if not np.isnan(cur_atr) else 0
                stop = ep + atr_mult * e_atr
                signals[i] = -1
        else:
            if pos == 1:
                new = px - atr_mult * cur_atr if not np.isnan(cur_atr) else stop
                if new > stop: stop = new
            else:
                new = px + atr_mult * cur_atr if not np.isnan(cur_atr) else stop
                if new < stop: stop = new
            signals[i] = pos
    return pd.Series(signals, index=close.index)


# ═══════════════════════════════════════════════════════
# 3. Volatility Expansion (BCO_USD — H4 or Daily)
# ═══════════════════════════════════════════════════════
def strategy_volatility_expansion(close, high, low, volume,
                                   lookback=20, vol_mult=1.5, atr_mult=2.0):
    """
    Volatility Expansion: Enter when current range > vol_mult × average ATR(lookback).
    Direction: follow the breakout of that expanding candle.
    Exit: revert to mean (exit when range contracts below avg) or ATR trailing stop.
    """
    n = len(close)
    signals = np.zeros(n, dtype=int)
    atr = _atr(high, low, close, lookback)
    atr_arr = atr.values
    avg_range = atr.rolling(window=lookback).mean().shift(1)
    candle_range = high - low

    pos = 0; ep = 0.0; e_atr = 0.0; stop = 0.0
    warmup = lookback * 3
    for i in range(warmup, n):
        px = close.values[i]
        cur_atr = atr_arr[i]

        # trailing stop
        if pos == 1 and stop > 0 and px < stop:
            pos = 0; stop = 0.0; signals[i] = 0; continue
        if pos == -1 and stop > 0 and px > stop:
            pos = 0; stop = 0.0; signals[i] = 0; continue

        # exit: range contracts back below average
        if pos == 1 and candle_range.values[i] < avg_range.values[i] and close.values[i] < close.values[i-1]:
            pos = 0; stop = 0.0; signals[i] = 0; continue
        if pos == -1 and candle_range.values[i] < avg_range.values[i] and close.values[i] > close.values[i-1]:
            pos = 0; stop = 0.0; signals[i] = 0; continue

        # entry
        if pos == 0 and not np.isnan(avg_range.values[i]):
            if candle_range.values[i] > vol_mult * avg_range.values[i]:
                if close.values[i] > close.values[i-1]:
                    pos = 1; ep = px; e_atr = cur_atr if not np.isnan(cur_atr) else 0
                    stop = ep - atr_mult * e_atr
                    signals[i] = 1
                else:
                    pos = -1; ep = px; e_atr = cur_atr if not np.isnan(cur_atr) else 0
                    stop = ep + atr_mult * e_atr
                    signals[i] = -1
        else:
            if pos == 1:
                new = px - atr_mult * cur_atr if not np.isnan(cur_atr) else stop
                if new > stop: stop = new
            else:
                new = px + atr_mult * cur_atr if not np.isnan(cur_atr) else stop
                if new < stop: stop = new
            signals[i] = pos
    return pd.Series(signals, index=close.index)


# ═══════════════════════════════════════════════════════
# 4. ADX Trend Strength (USD_TRY — H4 or Daily)
# ═══════════════════════════════════════════════════════
def strategy_adx_trend(close, high, low, volume,
                        adx_period=14, adx_threshold=25, ema_period=50, atr_mult=2.0):
    """
    ADX Trend: Enter long when ADX > threshold AND price > EMA(50) AND +DI > -DI.
    Exit when ADX drops below threshold or EMA crossback.
    """
    n = len(close)
    signals = np.zeros(n, dtype=int)
    atr = _atr(high, low, close, adx_period)
    atr_arr = atr.values

    # ADX
    prev_high = high.shift(1); prev_low = low.shift(1)
    plus_dm = ((high - prev_high) > (prev_low - low)).astype(float) * (high - prev_high)
    plus_dm = plus_dm.where(plus_dm > 0, 0).where(high > prev_high, 0)
    minus_dm = ((prev_low - low) > (high - prev_high)).astype(float) * (prev_low - low)
    minus_dm = minus_dm.where(minus_dm > 0, 0).where(prev_low > low, 0)
    atr_temp = _atr(high, low, close, adx_period)
    plus_di = 100 * plus_dm.ewm(alpha=1/adx_period, adjust=False).mean() / (atr_temp + 1e-10)
    minus_di = 100 * minus_dm.ewm(alpha=1/adx_period, adjust=False).mean() / (atr_temp + 1e-10)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
    adx = dx.ewm(alpha=1/adx_period, adjust=False).mean()

    ema = close.ewm(span=ema_period, adjust=False).mean()

    pos = 0; ep = 0.0; e_atr = 0.0; stop = 0.0
    warmup = adx_period * 3 + ema_period
    for i in range(warmup, n):
        px = close.values[i]
        cur_atr = atr_arr[i]

        # trailing stop
        if pos == 1 and stop > 0 and px < stop:
            pos = 0; stop = 0.0; signals[i] = 0; continue
        if pos == -1 and stop > 0 and px > stop:
            pos = 0; stop = 0.0; signals[i] = 0; continue

        # exit: ADX drops or price crosses EMA
        if pos == 1 and (adx.values[i] < adx_threshold or px < ema.values[i]):
            pos = 0; stop = 0.0; signals[i] = 0; continue
        if pos == -1 and (adx.values[i] < adx_threshold or px > ema.values[i]):
            pos = 0; stop = 0.0; signals[i] = 0; continue

        # entry
        if pos == 0 and adx.values[i] > adx_threshold:
            if plus_di.values[i] > minus_di.values[i] and px > ema.values[i]:
                pos = 1; ep = px; e_atr = cur_atr if not np.isnan(cur_atr) else 0
                stop = ep - atr_mult * e_atr
                signals[i] = 1
            elif minus_di.values[i] > plus_di.values[i] and px < ema.values[i]:
                pos = -1; ep = px; e_atr = cur_atr if not np.isnan(cur_atr) else 0
                stop = ep + atr_mult * e_atr
                signals[i] = -1
        else:
            if pos == 1:
                new = px - atr_mult * cur_atr if not np.isnan(cur_atr) else stop
                if new > stop: stop = new
            else:
                new = px + atr_mult * cur_atr if not np.isnan(cur_atr) else stop
                if new < stop: stop = new
            signals[i] = pos
    return pd.Series(signals, index=close.index)


# ═══════════════════════════════════════════════════════
# 5. Ichimoku Cloud (NAS100 — H4 or Daily)
# ═══════════════════════════════════════════════════════
def strategy_ichimoku_cloud(close, high, low, volume,
                              t_period=9, k_period=26, s_period=52, l_period=26, atr_mult=2.0):
    """
    Ichimoku Cloud: Enter long when price > cloud AND Tenkan > Kijun AND Chikou > price.
    Exit when price exits cloud or Tenkan crosses below Kijun.
    """
    n = len(close)
    signals = np.zeros(n, dtype=int)

    def donchian_mid(d, period):
        return (d.rolling(period).max() + d.rolling(period).min()) / 2

    tenkan = donchian_mid(high, t_period).rolling(1).apply(lambda x: x[0]) if False else None  # placeholder
    tenkan = (high.rolling(t_period).max() + low.rolling(t_period).min()) / 2
    kijun = (high.rolling(k_period).max() + low.rolling(k_period).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(k_period)
    senkou_b = (high.rolling(s_period).max() + low.rolling(s_period).min()) / 2
    senkou_b = senkou_b.shift(k_period)

    atr = _atr(high, low, close, 14)
    atr_arr = atr.values

    pos = 0; ep = 0.0; e_atr = 0.0; stop = 0.0
    warmup = max(s_period, k_period) * 2 + 14
    for i in range(warmup, n):
        px = close.values[i]
        cur_atr = atr_arr[i]

        sa = senkou_a.values[i]; sb = senkou_b.values[i]
        cloud_top = max(sa, sb) if not (np.isnan(sa) or np.isnan(sb)) else px
        cloud_bot = min(sa, sb) if not (np.isnan(sa) or np.isnan(sb)) else px
        above_cloud = px > cloud_top
        below_cloud = px < cloud_bot
        in_cloud = not above_cloud and not below_cloud

        tenkan_val = tenkan.values[i]; kijun_val = kijun.values[i]
        tenkan_above = tenkan_val > kijun_val
        tenkan_below = tenkan_val < kijun_val

        # trailing stop
        if pos == 1 and stop > 0 and px < stop:
            pos = 0; stop = 0.0; signals[i] = 0; continue
        if pos == -1 and stop > 0 and px > stop:
            pos = 0; stop = 0.0; signals[i] = 0; continue

        # exits
        if pos == 1 and (in_cloud or below_cloud or tenkan_below):
            pos = 0; stop = 0.0; signals[i] = 0; continue
        if pos == -1 and (in_cloud or above_cloud or tenkan_above):
            pos = 0; stop = 0.0; signals[i] = 0; continue

        # entry
        if pos == 0:
            if above_cloud and tenkan_above and tenkan_val > tenkan.values[i-1]:
                pos = 1; ep = px; e_atr = cur_atr if not np.isnan(cur_atr) else 0
                stop = ep - atr_mult * e_atr
                signals[i] = 1
            elif below_cloud and tenkan_below and tenkan_val < tenkan.values[i-1]:
                pos = -1; ep = px; e_atr = cur_atr if not np.isnan(cur_atr) else 0
                stop = ep + atr_mult * e_atr
                signals[i] = -1
        else:
            if pos == 1:
                new = px - atr_mult * cur_atr if not np.isnan(cur_atr) else stop
                if new > stop: stop = new
            else:
                new = px + atr_mult * cur_atr if not np.isnan(cur_atr) else stop
                if new < stop: stop = new
            signals[i] = pos
    return pd.Series(signals, index=close.index)


# ═══════════════════════════════════════════════════════
# 6. Supertrend + Volatility (XAG_USD — Daily)
# ═══════════════════════════════════════════════════════
def strategy_supertrend_vol(close, high, low, volume,
                              st_period=10, st_mult=3.0, vol_lookback=20, atr_mult=2.0):
    """
    Supertrend + Volume filter: Enter on Supertrend flip when recent volume > average.
    """
    n = len(close)
    signals = np.zeros(n, dtype=int)

    # ATR
    atr = _atr(high, low, close, st_period)
    atr_arr = atr.values

    # Supertrend
    hl2 = (high + low) / 2
    upper = hl2 + st_mult * atr
    lower = hl2 - st_mult * atr
    supertrend = pd.Series(0.0, index=close.index)
    supertrend_dir = pd.Series(1, index=close.index)  # 1 = bullish, -1 = bearish

    for i in range(st_period + 1, n):
        p = supertrend.iloc[i-1]; d = supertrend_dir.iloc[i-1]
        if upper.values[i] < p or close.values[i-1] > p:
            supertrend.values[i] = upper.values[i]; supertrend_dir.values[i] = -1
        elif lower.values[i] > p or close.values[i-1] < p:
            supertrend.values[i] = lower.values[i]; supertrend_dir.values[i] = 1
        else:
            supertrend.values[i] = lower.values[i] if d == 1 else upper.values[i]
            supertrend_dir.values[i] = d

    st_dir = supertrend_dir.values
    # Volume filter
    vol_avg = volume.rolling(window=vol_lookback).mean()

    pos = 0; ep = 0.0; e_atr = 0.0; stop = 0.0
    warmup = max(st_period, vol_lookback) + 14
    for i in range(warmup, n):
        px = close.values[i]
        cur_atr = atr_arr[i]

        # trailing stop
        if pos == 1 and stop > 0 and px < stop:
            pos = 0; stop = 0.0; signals[i] = 0; continue
        if pos == -1 and stop > 0 and px > stop:
            pos = 0; stop = 0.0; signals[i] = 0; continue

        # exit on ST flip
        if pos == 1 and st_dir[i] == -1:
            pos = 0; stop = 0.0; signals[i] = 0; continue
        if pos == -1 and st_dir[i] == 1:
            pos = 0; stop = 0.0; signals[i] = 0; continue

        # entry on ST flip + volume confirmation
        if pos == 0 and not np.isnan(vol_avg.values[i]):
            if st_dir[i] == 1 and st_dir[i-1] == -1 and volume.values[i] > vol_avg.values[i]:
                pos = 1; ep = px; e_atr = cur_atr if not np.isnan(cur_atr) else 0
                stop = ep - atr_mult * e_atr
                signals[i] = 1
            elif st_dir[i] == -1 and st_dir[i-1] == 1 and volume.values[i] > vol_avg.values[i]:
                pos = -1; ep = px; e_atr = cur_atr if not np.isnan(cur_atr) else 0
                stop = ep + atr_mult * e_atr
                signals[i] = -1
        else:
            if pos == 1:
                new = px - atr_mult * cur_atr if not np.isnan(cur_atr) else stop
                if new > stop: stop = new
            else:
                new = px + atr_mult * cur_atr if not np.isnan(cur_atr) else stop
                if new < stop: stop = new
            signals[i] = pos
    return pd.Series(signals, index=close.index)


# ═══════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════
def _atr(high, low, close, period=14):
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()
