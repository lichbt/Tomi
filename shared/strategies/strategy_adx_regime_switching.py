"""ADX Dual-Regime Adaptive System.

Author: Strategy Coder Agent

Core Logic:
  - ADX(14) > 27 (with hysteresis exit at 22) → Trend regime → Donchian breakout.
  - ADX(14) < 20 (with hysteresis exit at 25) → Range regime → Bollinger mean reversion.
  - 20 <= ADX <= 27 → Transition → stay flat or hold existing position.
  - Exit: Regime change OR ATR trailing stop (2.5x default).
"""
from __future__ import annotations

import pandas as pd
import numpy as np


def _true_range(
    high: pd.Series, low: pd.Series, close: pd.Series
) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def _directional_movement(
    high: pd.Series, low: pd.Series, period: int = 14
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Compute +DI, -DI, and ADX."""
    up = high.diff()
    down = -low.diff()

    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    tr = _true_range(high, low, high.shift(1))
    atr = tr.rolling(period).mean()

    plus_di = 100.0 * pd.Series(plus_dm, index=high.index).rolling(period).mean() / (
        atr + 1e-9
    )
    minus_di = 100.0 * pd.Series(minus_dm, index=high.index).rolling(period).mean() / (
        atr + 1e-9
    )

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
    adx = dx.rolling(period).mean()

    return plus_di, minus_di, adx


def strategy_adx_regime_switching(
    df: pd.DataFrame, params: dict
) -> pd.Series[int]:
    """ADX-based dual-regime strategy (trend breakout + range mean-reversion).

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: ['open', 'high', 'low', 'close', 'volume'].
    params : dict
        - adx_period : int, optional (default 14)
        - trend_enter_thresh : float, optional (default 27)
        - trend_exit_thresh : float, optional (default 22)
        - range_enter_thresh : float, optional (default 20)
        - range_exit_thresh : float, optional (default 25)
        - dc_period : int, optional (default 20) — Donchian channel period
        - bb_period : int, optional (default 20)
        - bb_std : float, optional (default 2.0)
        - atr_period : int, optional (default 14)
        - stop_atr_mult : float, optional (default 2.5)

    Returns
    -------
    pd.Series
        Integer signals: 1 = long, -1 = short, 0 = flat.
        Shifted by 1 bar to prevent look-ahead bias.
    """
    # --- Extract columns ---------------------------------------------------------
    high = df["high"].astype(np.float64)
    low = df["low"].astype(np.float64)
    close = df["close"].astype(np.float64)

    # --- Parameters ---------------------------------------------------------------
    adx_period = params.get("adx_period", 14)
    trend_enter_thresh = params.get("trend_enter_thresh", 27)
    trend_exit_thresh = params.get("trend_exit_thresh", 22)
    range_enter_thresh = params.get("range_enter_thresh", 20)
    range_exit_thresh = params.get("range_exit_thresh", 25)
    dc_period = params.get("dc_period", 20)
    bb_period = params.get("bb_period", 20)
    bb_std = params.get("bb_std", 2.0)
    atr_period = params.get("atr_period", 14)
    stop_atr_mult = params.get("stop_atr_mult", 2.5)
    risk_model = params.get('risk_model', 'baseline')
    if risk_model == 'breakeven':
        breakeven_atr = params.get('breakeven_atr', 2.0)
        breakeven_buffer = params.get('breakeven_buffer', 0.5)
    elif risk_model == 'percent_trail':
        profit_switch_atr = params.get('profit_switch_atr', 4.0)
        percent_trail = params.get('percent_trail', 0.02)

    # --- Indicators ----------------------------------------------------------------
    _, _, adx = _directional_movement(high, low, adx_period)

    # Donchian channels (trend mode)
    dc_high = high.rolling(dc_period).max()
    dc_low = low.rolling(dc_period).min()

    # Bollinger Bands (range mode)
    bb_mid = close.rolling(bb_period).mean()
    bb_std_dev = close.rolling(bb_period).std(ddof=0)
    bb_upper = bb_mid + bb_std * bb_std_dev
    bb_lower = bb_mid - bb_std * bb_std_dev

    # ATR
    tr = _true_range(high, low, close)
    atr = tr.rolling(atr_period).mean()

    # --- Regime classification with hysteresis ------------------------------------
    # Track previous regime to implement hysteresis
    # Entered trend: ADX > 27, stays in trend until ADX < 22
    # Entered range: ADX < 20, stays in range until ADX > 25

    # --- Signal generation loop ---------------------------------------------------
    signals = pd.Series(0, index=df.index)
    position = 0
    peak = 0.0
    trough = 0.0
    entry_price = 0.0
    regime = "NEUTRAL"  # TREND, RANGE, or NEUTRAL

    lookback = max(adx_period * 2, dc_period, bb_period, atr_period) + 2

    for i in range(lookback, len(df)):
        if pd.isna(atr.iloc[i]) or atr.iloc[i] <= 0 or pd.isna(adx.iloc[i]):
            signals.iloc[i] = position
            continue

        cur_high = high.iloc[i]
        cur_low = low.iloc[i]
        cur_close = close.iloc[i]
        cur_atr = atr.iloc[i]
        cur_adx = adx.iloc[i]

        # --- Regime transitions with hysteresis -----------------------------------
        if regime == "TREND":
            if cur_adx < trend_exit_thresh:
                regime = "NEUTRAL"
        elif regime == "RANGE":
            if cur_adx > range_exit_thresh:
                regime = "NEUTRAL"
        else:  # NEUTRAL
            if cur_adx > trend_enter_thresh:
                regime = "TREND"
            elif cur_adx < range_enter_thresh:
                regime = "RANGE"

        # --- Exit logic (trailing stop + regime change) --------------------------
        exited = False
        if position == 1:  # Long
            peak = max(peak, cur_high)
            trail_stop = peak - stop_atr_mult * cur_atr
            # Risk model adjustments
            if risk_model == 'breakeven':
                profit = cur_close - entry_price
                if profit >= breakeven_atr * cur_atr:
                    trail_stop = max(trail_stop, entry_price + breakeven_buffer * cur_atr)
            elif risk_model == 'percent_trail':
                profit = cur_close - entry_price
                if profit >= profit_switch_atr * cur_atr:
                    trail_stop = peak * (1 - percent_trail)
            if cur_low <= trail_stop:
                position = 0
                exited = True
            elif regime == "RANGE":
                position = 0
                exited = True
        elif position == -1:  # Short
            trough = min(trough, cur_low)
            trail_stop = trough + stop_atr_mult * cur_atr
            if risk_model == 'breakeven':
                profit = entry_price - cur_close
                if profit >= breakeven_atr * cur_atr:
                    trail_stop = min(trail_stop, entry_price - breakeven_buffer * cur_atr)
            elif risk_model == 'percent_trail':
                profit = entry_price - cur_close
                if profit >= profit_switch_atr * cur_atr:
                    trail_stop = trough * (1 + percent_trail)
            if cur_high >= trail_stop:
                position = 0
                exited = True
            elif regime == "RANGE":
                position = 0
                exited = True

        # --- Entry logic (only when flat) -----------------------------------------
        if position == 0 and regime != "NEUTRAL":
            if regime == "TREND":
                # Donchian breakout
                if cur_close > dc_high.shift(1).iloc[i] if pd.notna(dc_high.shift(1).iloc[i]) else False:
                    position = 1
                    entry_price = cur_close
                    peak = cur_high
                elif cur_close < dc_low.shift(1).iloc[i] if pd.notna(dc_low.shift(1).iloc[i]) else False:
                    position = -1
                    entry_price = cur_close
                    trough = cur_low
            elif regime == "RANGE":
                # Bollinger mean reversion
                if cur_close < bb_lower.iloc[i]:
                    position = 1
                    entry_price = cur_close
                    peak = cur_high
                elif cur_close > bb_upper.iloc[i]:
                    position = -1
                    entry_price = cur_close
                    trough = cur_low

        signals.iloc[i] = position

    return signals.astype(int).shift(1).fillna(0).astype(int)
