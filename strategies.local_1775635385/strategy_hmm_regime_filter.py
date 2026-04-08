"""
HMM Regime Filter Strategy

A regime-aware trading strategy using a Hidden Markov Model (HMM) to detect
market regimes (bull_trend, bear_trend, ranging) and apply regime-specific
entry/exit logic with ATR trailing stops.

Entry/Exit Logic by Regime:
  - BULL_TREND: LONG when EMA slope up + RSI < 70; SHORT when RSI > 80
  - BEAR_TREND: SHORT when EMA slope down + RSI > 30; LONG when RSI < 20
  - RANGING:   Mean reversion — LONG when RSI < 35, SHORT when RSI > 65

All indicators are shifted by 1 bar to prevent lookahead bias.
"""

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler


def strategy_hmm_regime_filter(
    close, high, low, volume,
    lookback=20, hmm_states=3, ema_period=20, rsi_period=14
):
    """
    Generate regime-aware trading signals using HMM + ATR trailing stop.

    Parameters
    ----------
    close : pd.Series
        Closing prices.
    high : pd.Series
        High prices.
    low : pd.Series
        Low prices.
    volume : pd.Series
        Volume (unused in signal logic but kept for signature compatibility).
    lookback : int, default 20
        Rolling window size for HMM feature (log-return volatility).
    hmm_states : int, default 3
        Number of hidden states in the HMM (bull, bear, ranging).
    ema_period : int, default 20
        EMA period for trend detection.
    rsi_period : int, default 14
        RSI period for momentum measurement.

    Returns
    -------
    pd.Series
        Signal series: 1 = long, -1 = short, 0 = flat/exit.
    """
    # ── Minimum data check ──────────────────────────────────────────────────
    min_required = lookback + 52
    if len(close) < min_required:
        return pd.Series(0, index=close.index)

    close = close.copy()
    high  = high.copy()
    low   = low.copy()

    # ── Indicators (computed on full series, shifted later) ─────────────────

    # 1) Log returns
    log_ret = np.log(close / close.shift(1))

    # 2) Rolling volatility of log returns
    rolling_vol = log_ret.rolling(lookback).std()

    # 3) EMA
    ema = close.ewm(span=ema_period, adjust=False).mean()

    # 4) EMA slope (percent change over ema_period)
    ema_slope = ema.pct_change(ema_period)

    # 5) RSI
    delta = close.diff()
    gain  = delta.where(delta > 0, 0.0).ewm(alpha=1 / rsi_period, adjust=False).mean()
    loss  = (-delta.where(delta < 0, 0.0)).ewm(alpha=1 / rsi_period, adjust=False).mean()
    rs    = gain / loss.replace(0, np.inf)
    rsi   = 100 - (100 / (1 + rs))

    # 6) ATR(14)
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    # ── Build HMM features ──────────────────────────────────────────────────
    # Align log_ret and rolling_vol by dropping NaN rows
    feats_df = pd.DataFrame({"log_ret": log_ret, "rolling_vol": rolling_vol}).dropna()

    if len(feats_df) < hmm_states * 10:  # rough sanity check
        return pd.Series(0, index=close.index)

    X = feats_df.values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Fit Gaussian HMM on full series
    model = GaussianHMM(
        n_components=hmm_states,
        covariance_type="full",
        n_iter=1000,
        random_state=42
    )
    model.fit(X_scaled)

    # Viterbi decode — get most likely state sequence
    state_seq = model.predict(X_scaled)   # array of shape (n_samples,)

    # ── Map states to regime labels ─────────────────────────────────────────
    # Reconstruct log_ret per state to compute mean return per state
    feats_df["state"] = state_seq
    state_mean_ret = feats_df.groupby("state")["log_ret"].mean()

    sorted_states = state_mean_ret.sort_values(ascending=False)
    bull_state   = sorted_states.index[0]   # highest mean return
    bear_state   = sorted_states.index[-1]  # lowest mean return

    # Build regime label series and REINDEX to close.index to avoid iloc bounds error
    regime_label = pd.Series(index=feats_df.index, dtype=int)
    for idx in feats_df.index:
        s = feats_df.loc[idx, "state"]
        if s == bull_state:
            regime_label[idx] = 1   # bull_trend
        elif s == bear_state:
            regime_label[idx] = -1  # bear_trend
        else:
            regime_label[idx] = 0   # ranging

    # CRITICAL FIX: reindex to close.index before shift() so length matches close
    regime_label = regime_label.reindex(close.index).ffill().fillna(0).astype(int)

    # ── Shifted indicators for signal generation ────────────────────────────
    ema_s       = ema.shift(1)
    ema_slope_s = ema_slope.shift(1)
    rsi_s       = rsi.shift(1)
    atr_s       = atr.shift(1)
    regime_s    = regime_label.shift(1)  # can't trade today's regime until tomorrow

    # ── Signal generation with explicit position tracking ───────────────────
    n = len(close)
    signals = pd.Series(0, index=close.index)
    position = 0          # 1 = long, -1 = short, 0 = flat
    entry_price = np.nan
    long_stop_price  = np.nan
    short_stop_price = np.nan

    for i in range(1, n):
        price   = close.iloc[i]
        regime  = regime_s.iloc[i]
        es      = ema_s.iloc[i]
        ess     = ema_slope_s.iloc[i]
        rsii    = rsi_s.iloc[i]
        atr_val = atr_s.iloc[i]

        # Skip if any indicator is NaN
        if pd.isna(regime) or pd.isna(es) or pd.isna(ess) or pd.isna(rsii) or pd.isna(atr_val):
            continue

        # ── ATR Trailing Stop ──────────────────────────────────────────────
        if position == 1 and not np.isnan(entry_price):
            new_stop = price - 2.5 * atr_val
            long_stop_price = max(long_stop_price, new_stop) if not np.isnan(long_stop_price) else new_stop
            if price <= long_stop_price:
                position = 0
                signals.iloc[i] = 0
                entry_price = np.nan
                long_stop_price = np.nan
                short_stop_price = np.nan
                continue

        elif position == -1 and not np.isnan(entry_price):
            new_stop = price + 2.5 * atr_val
            short_stop_price = min(short_stop_price, new_stop) if not np.isnan(short_stop_price) else new_stop
            if price >= short_stop_price:
                position = 0
                signals.iloc[i] = 0
                entry_price = np.nan
                long_stop_price = np.nan
                short_stop_price = np.nan
                continue

        # ── Entry Signals ──────────────────────────────────────────────────
        if regime == 1:   # BULL_TREND
            if position == 0:
                # LONG: EMA slope up AND RSI < 70
                if ess > 0 and rsii < 70:
                    position = 1
                    entry_price = price
                    long_stop_price  = price - 2.5 * atr_val
                    short_stop_price = np.nan
                    signals.iloc[i] = 1
                # SHORT (counter-trend, tight filter): RSI > 80
                elif rsii > 80:
                    position = -1
                    entry_price = price
                    short_stop_price = price + 2.5 * atr_val
                    long_stop_price  = np.nan
                    signals.iloc[i] = -1

            elif position == 1:
                # Maintain long; check for early exit if RSI overbought
                if rsii > 80:
                    position = 0
                    signals.iloc[i] = 0
                    entry_price = np.nan
                    long_stop_price = np.nan
                    short_stop_price = np.nan
                else:
                    signals.iloc[i] = 1

            elif position == -1:
                signals.iloc[i] = -1

        elif regime == -1:  # BEAR_TREND
            if position == 0:
                # SHORT: EMA slope down AND RSI > 30
                if ess < 0 and rsii > 30:
                    position = -1
                    entry_price = price
                    short_stop_price = price + 2.5 * atr_val
                    long_stop_price  = np.nan
                    signals.iloc[i] = -1
                # LONG (counter-trend, extreme only): RSI < 20
                elif rsii < 20:
                    position = 1
                    entry_price = price
                    long_stop_price  = price - 2.5 * atr_val
                    short_stop_price = np.nan
                    signals.iloc[i] = 1

            elif position == -1:
                # Maintain short; exit if RSI oversold
                if rsii < 20:
                    position = 0
                    signals.iloc[i] = 0
                    entry_price = np.nan
                    short_stop_price = np.nan
                    long_stop_price = np.nan
                else:
                    signals.iloc[i] = -1

            elif position == 1:
                signals.iloc[i] = 1

        else:  # RANGING regime
            if position == 0:
                if rsii < 35:
                    position = 1
                    entry_price = price
                    long_stop_price  = price - 2.5 * atr_val
                    short_stop_price = np.nan
                    signals.iloc[i] = 1
                elif rsii > 65:
                    position = -1
                    entry_price = price
                    short_stop_price = price + 2.5 * atr_val
                    long_stop_price  = np.nan
                    signals.iloc[i] = -1

            elif position == 1:
                # Exit long when RSI crosses back above 50 (mean-reversion exit)
                if rsii >= 50:
                    position = 0
                    signals.iloc[i] = 0
                    entry_price = np.nan
                    long_stop_price = np.nan
                    short_stop_price = np.nan
                else:
                    signals.iloc[i] = 1

            elif position == -1:
                # Exit short when RSI crosses back below 50
                if rsii <= 50:
                    position = 0
                    signals.iloc[i] = 0
                    entry_price = np.nan
                    short_stop_price = np.nan
                    long_stop_price = np.nan
                else:
                    signals.iloc[i] = -1

    return signals
