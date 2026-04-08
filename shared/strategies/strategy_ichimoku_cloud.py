"""Ichimoku Cloud Strategy.

Uses the full Ichimoku Kinko Hyo system:
- Tenkan-sen (conversion line) / Kijun-sen (base line) cross
- Price relative to Kumo (cloud) for trend filter
- Chikou span (lagging span) confirmation
- Senkou Span A/B for cloud boundaries

Signal convention: +1 = long, -1 = short, 0 = flat.
"""
import pandas as pd
import numpy as np


def strategy_ichimoku_cloud(df: pd.DataFrame, params: dict) -> pd.Series:
    """Ichimoku Cloud trend-following strategy.

    Entry signals:
    - Long: Tenkan > Kijun + price above cloud + Chikou above price (26 bars back)
    - Short: Tenkan < Kijun + price below cloud + Chikou below price (26 bars back)

    Exits on ATR trailing stop or signal reversal.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ['open', 'high', 'low', 'close'].
    params : dict
        tenkan_period    : int   - Conversion line period (default 9)
        kijun_period     : int   - Base line period (default 26)
        senkou_b_period  : int   - Leading Span B period (default 52)
        chikou_displace  : int   - Lagging span displacement (default 26)
        atr_period       : int   - ATR window for stops (default 14)
        stop_mult        : float - ATR multiplier for trailing stop (default 2.0)
        require_cloud    : bool  - Require price outside cloud for entry (default True)

    Returns
    -------
    pd.Series[int]
        Signal series shifted by 1 to prevent look-ahead bias.
    """
    tenkan_period = params.get('tenkan_period', 9)
    kijun_period = params.get('kijun_period', 26)
    senkou_b_period = params.get('senkou_b_period', 52)
    chikou_displace = params.get('chikou_displace', 26)
    atr_period = params.get('atr_period', 14)
    stop_mult = params.get('stop_mult', 2.0)
    require_cloud = params.get('require_cloud', True)
    risk_model = params.get('risk_model', 'baseline')
    if risk_model == 'breakeven':
        breakeven_atr = params.get('breakeven_atr', 2.0)
        breakeven_buffer = params.get('breakeven_buffer', 0.5)
    elif risk_model == 'percent_trail':
        profit_switch_atr = params.get('profit_switch_atr', 4.0)
        percent_trail = params.get('percent_trail', 0.02)

    high = df['high'].astype(np.float64)
    low = df['low'].astype(np.float64)
    close = df['close'].astype(np.float64)
    prev_close = close.shift(1)

    def _midline(window: int) -> pd.Series:
        return (df['high'].rolling(window).max() + df['low'].rolling(window).min()) / 2.0

    # Ichimoku components
    tenkan = _midline(tenkan_period)
    kijun = _midline(kijun_period)
    senkou_a = ((tenkan + kijun) / 2.0).shift(chikou_displace)
    senkou_b = _midline(senkou_b_period).shift(chikou_displace)
    chikou = close.shift(-chikou_displace)

    # Cloud boundaries
    cloud_top = senkou_a.where(senkou_a > senkou_b, senkou_b)
    cloud_bottom = senkou_b.where(senkou_a > senkou_b, senkou_a)

    # ATR for stops
    tr = pd.concat([high - low, abs(high - prev_close), abs(low - prev_close)], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    # Signals
    signals = pd.Series(0, index=df.index, dtype=int)
    position = 0
    peak = 0.0
    trough = 0.0
    entry_price = 0.0

    start_idx = max(senkou_b_period + chikou_displace, atr_period, tenkan_period)
    end_idx = len(df) - chikou_displace  # Can't use Chikou beyond available data

    for i in range(start_idx, min(end_idx, len(df))):
        if np.isnan(atr.iloc[i]) or atr.iloc[i] <= 0:
            signals.iloc[i] = position
            continue

        # Trailing stop exit
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

        if position == 0:
            tenkan_val = tenkan.iloc[i]
            kijun_val = kijun.iloc[i]
            chikou_val = chikou.iloc[i]
            price_val = close.iloc[i]

            # Long: TK cross up + above cloud + Chikou confirms
            long_signal = (tenkan_val > kijun_val) and (price_val > cloud_top.iloc[i])
            if require_cloud:
                long_signal = long_signal and (chikou_val > close.iloc[i - chikou_displace] if i >= chikou_displace else True)

            # Short: TK cross down + below cloud + Chikou confirms
            short_signal = (tenkan_val < kijun_val) and (price_val < cloud_bottom.iloc[i])
            if require_cloud:
                short_signal = short_signal and (chikou_val < close.iloc[i - chikou_displace] if i >= chikou_displace else True)

            if long_signal:
                position = 1
                entry_price = close.iloc[i]
                peak = high.iloc[i]
            elif short_signal:
                position = -1
                entry_price = close.iloc[i]
                trough = low.iloc[i]

        signals.iloc[i] = position

    return signals.shift(1).fillna(0).astype(int)
