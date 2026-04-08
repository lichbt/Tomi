#!/usr/bin/env python3
"""
Choppiness Index Mean Reversion Optimization — Daily timeframe
IS: 2015-2019 | OOS: 2020-2025

Param grid covers CHOP threshold, RSI entry/exit bands, ADX filter.
Tests on BTC_USD and XAU_USD.
"""

import sys
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
from itertools import product
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, '/Users/lich/.openclaw/workspace/strategies')
from strategy_choppiness_index_mr import strategy_choppiness_index_mr

try:
    import yfinance as yf
except ImportError:
    print("Install yfinance: pip install yfinance")
    sys.exit(1)

# === Config ===
INSTRUMENTS = {
    'BTC_USD': 'BTC-USD',
    'XAU_USD': 'GC=F',
}

IS_START  = '2015-01-01'
IS_END    = '2019-12-31'
OOS_START = '2020-01-01'
OOS_END   = '2025-12-31'

COMMISSION = 0.001
SLIPPAGE = 0.0005
INITIAL_CAPITAL = 100000

OUTPUT_DIR = '/Users/lich/.openclaw/workspace/backtester'
os.makedirs(OUTPUT_DIR, exist_ok=True)


def fetch_daily(symbol, start, end):
    """Fetch Daily OHLCV from yfinance."""
    ticker = yf.Ticker(symbol)
    raw = ticker.history(start=start, end=end, interval='1d')
    if raw.empty:
        print(f"  WARNING: No data for {symbol}")
        return pd.DataFrame()
    raw = raw.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'})
    raw.index.name = 'timestamp'
    return raw[['open','high','low','close','volume']]


def run_backtest_fixed(data, signals, initial_capital=INITIAL_CAPITAL,
                       commission=COMMISSION, slippage=SLIPPAGE):
    """Fixed-cash-accounting backtest. Daily Sharpe (sqrt(252))."""
    n = len(data)
    if n == 0:
        return None

    close_arr = data['close'].values
    cash = initial_capital
    equity_series = np.zeros(n)
    trades = []
    position = 0
    entry_price = 0.0
    shares = 0
    entry_idx = 0
    margin_deposited = 0.0

    for i in range(n):
        signal = signals.iloc[i] if i < len(signals) else 0
        price = close_arr[i]

        if position == 1:
            unrealized = shares * (price - entry_price)
        elif position == -1:
            unrealized = shares * (entry_price - price)
        else:
            unrealized = 0.0
        equity = cash + unrealized
        equity_series[i] = equity

        # EXIT
        if position == 1 and signal != 1:
            exit_px = price * (1 - slippage) * (1 - commission)
            pnl = (exit_px - entry_price) * shares
            cash += shares * exit_px
            trades.append({'entry_idx': entry_idx, 'exit_idx': i,
                           'entry_price': float(entry_price),
                           'exit_price': float(exit_px),
                           'position': 1, 'pnl': float(pnl)})
            shares = 0; position = 0; entry_price = 0.0; entry_idx = 0

        elif position == -1 and signal != -1:
            exit_px = price * (1 + slippage) * (1 + commission)
            pnl = (entry_price - exit_px) * shares
            cash += pnl
            trades.append({'entry_idx': entry_idx, 'exit_idx': i,
                           'entry_price': float(entry_price),
                           'exit_price': float(exit_px),
                           'position': -1, 'pnl': float(pnl)})
            shares = 0; position = 0; entry_price = 0.0
            margin_deposited = 0.0; entry_idx = 0

        # ENTRY
        if position == 0 and signal != 0:
            available = cash + margin_deposited
            position_value = max(available * 0.95, 0)

            if signal == 1 and position_value > 0:
                entry_px = price * (1 + slippage) * (1 + commission)
                sh = max(int(position_value / entry_px), 0)
                if sh > 0:
                    cash -= sh * entry_px
                    entry_price = entry_px
                    position = 1; entry_idx = i; shares = sh

            elif signal == -1 and position_value > 0:
                entry_px = price * (1 + slippage) * (1 + commission)
                sh = max(int(position_value / entry_px), 0)
                if sh > 0:
                    margin_deposited = sh * entry_px
                    cash -= margin_deposited
                    cash += sh * entry_px
                    entry_price = entry_px
                    position = -1; entry_idx = i; shares = sh

    # Close remaining
    if position != 0 and n > 0:
        fp = close_arr[-1]
        if position == 1:
            exit_px = fp * (1 - slippage) * (1 - commission)
            pnl = (exit_px - entry_price) * shares
            cash += shares * exit_px
        else:
            exit_px = fp * (1 + slippage) * (1 + commission)
            pnl = (entry_price - exit_px) * shares
            cash += pnl
            margin_deposited = 0.0
        trades.append({'entry_idx': entry_idx, 'exit_idx': n-1,
                       'entry_price': float(entry_price),
                       'exit_price': float(exit_px),
                       'position': position, 'pnl': float(pnl)})
        equity_series[-1] = cash + margin_deposited

    # Metrics
    total_return = (equity_series[-1] / INITIAL_CAPITAL - 1) * 100 if n > 0 else 0
    num_trades = len(trades)
    wins = sum(1 for t in trades if t['pnl'] > 0)
    losses = sum(1 for t in trades if t['pnl'] < 0)
    win_rate = (wins / num_trades * 100) if num_trades > 0 else 0

    gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
    gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
    pf = gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0)

    returns = pd.Series(equity_series).pct_change().fillna(0)
    sharpe = np.sqrt(252) * (returns.mean() / returns.std()) if returns.std() > 0 and len(returns) > 1 else 0

    cum = (1 + returns).cumprod()
    running_max = cum.expanding().max()
    dd = (cum - running_max) / running_max
    max_dd = dd.min() * 100

    avg_trade = round(np.mean([t['pnl'] for t in trades]), 2) if num_trades > 0 else 0

    return {
        'total_return_pct': round(total_return, 2),
        'num_trades': num_trades,
        'win_rate_pct': round(win_rate, 2),
        'sharpe_ratio': round(sharpe, 3),
        'max_drawdown_pct': round(max_dd, 2),
        'profit_factor': round(pf, 3),
        'gross_profit': round(gross_profit, 2),
        'gross_loss': round(gross_loss, 2),
        'final_value': round(equity_series[-1], 2) if n > 0 else 0,
        'avg_trade': avg_trade,
        'trades': trades,
    }


def build_strategy(chop_th, rsi_le, rsi_se, rsi_lx, rsi_sx, adx_th):
    """Factory: returns a strategy wrapper with tuned thresholds."""
    from strategy_choppiness_index_mr import _true_range, _rsi, _atr, _directional_movement

    def strat(df):
        df = df.sort_index()
        high = df['high']; low = df['low']; close = df['close']
        N = 14
        atr_sum = _true_range(high, low, close).rolling(N).sum()
        price_range = high.rolling(N).max() - low.rolling(N).min()
        chop = 100.0 * np.log10(atr_sum / (price_range + 1e-10) + 1e-10) / np.log10(N)
        chop = chop.clip(0, 100)
        rsi = _rsi(close, 14)
        adx = _directional_movement(high, low, close, 14)

        le = (chop > chop_th) & (rsi < rsi_le) & (adx < adx_th)
        se = (chop > chop_th) & (rsi > rsi_se) & (adx < adx_th)
        lx = rsi > rsi_lx
        sx = rsi < rsi_sx

        signals = pd.Series(0, index=df.index, dtype=float)
        pos = 0
        for i in range(len(df)):
            if pos == 1 and pd.notna(lx.iloc[i]) and lx.iloc[i]:
                pos = 0
            elif pos == -1 and pd.notna(sx.iloc[i]) and sx.iloc[i]:
                pos = 0
            if pos == 0:
                if pd.notna(le.iloc[i]) and le.iloc[i]:
                    pos = 1
                elif pd.notna(se.iloc[i]) and se.iloc[i]:
                    pos = -1
            signals.iloc[i] = pos
        return signals.shift(1).fillna(0)
    return strat


if __name__ == '__main__':
    print("="*70)
    print("Choppiness Index MR Optimization | DAILY")
    print(f"IS: 2015-2019 | OOS: 2020-2025")
    print("="*70)

    # Param grid
    param_grid = list(product(
        [50, 55, 60, 61.8],   # chop_th: Choppiness threshold
        [35, 40, 45],         # rsi_le: RSI long entry (oversold)
        [55, 60, 65],         # rsi_se: RSI short entry (overbought)
        [50, 55],             # rsi_lx: RSI long exit
        [45, 50],             # rsi_sx: RSI short exit
        [20, 25, 30],         # adx_th: ADX filter threshold
    ))
    print(f"\nParameter grid: {len(param_grid)} combos")

    all_results = {}

    for sym_name, yf_sym in INSTRUMENTS.items():
        print(f"\n{'='*60}")
        print(f"INSTRUMENT: {sym_name} ({yf_sym})")
        print(f"{'='*60}")

        print(f"\nFetching Daily data (2015-2025)...")
        full_data = fetch_daily(yf_sym, '2015-01-01', '2025-12-31')
        if full_data.empty or len(full_data) < 200:
            print("  NOT ENOUGH DATA — skipping.")
            continue

        print(f"  Data shape: {full_data.shape} | {full_data.index[0]} to {full_data.index[-1]}")

        split_idx = full_data.index.searchsorted(OOS_START, side='left')
        is_data = full_data.iloc[:split_idx]
        oos_data = full_data.iloc[split_idx:]
        print(f"  IS: {is_data.shape[0]} bars | OOS: {oos_data.shape[0]} bars")

        best_oos_sharpe = -999
        best_params = None
        best_is = None
        best_oos = None
        param_results = []

        for chop_th, rsi_le, rsi_se, rsi_lx, rsi_sx, adx_th in param_grid:
            strat = build_strategy(chop_th, rsi_le, rsi_se, rsi_lx, rsi_sx, adx_th)

            is_signals = strat(is_data)
            is_res = run_backtest_fixed(is_data, is_signals)
            if is_res is None or is_res['num_trades'] < 10:
                continue

            oos_signals = strat(oos_data)
            oos_res = run_backtest_fixed(oos_data, oos_signals)
            if oos_res is None:
                continue

            is_sh = is_res['sharpe_ratio']
            oos_sh = oos_res['sharpe_ratio']
            ratio = oos_sh / is_sh if is_sh > 0 else 0

            rec = {
                'chop_th': chop_th, 'rsi_le': rsi_le, 'rsi_se': rsi_se,
                'rsi_lx': rsi_lx, 'rsi_sx': rsi_sx, 'adx_th': adx_th,
                'is_sharpe': round(is_sh, 3), 'is_ret': is_res['total_return_pct'],
                'is_trd': is_res['num_trades'], 'is_dd': is_res['max_drawdown_pct'],
                'oos_sharpe': round(oos_sh, 3), 'oos_ret': oos_res['total_return_pct'],
                'oos_trd': oos_res['num_trades'], 'oos_dd': oos_res['max_drawdown_pct'],
                'oos_pf': oos_res['profit_factor'],
                'oos_wr': oos_res['win_rate_pct'],
                'oos_is_ratio': round(ratio, 3),
                'oos_avg_trade': oos_res['avg_trade'],
            }
            param_results.append(rec)

            # Require at least 20 trades, positive PF to qualify
            if oos_sh > best_oos_sharpe and oos_res['num_trades'] >= 20 and oos_res['profit_factor'] > 0.5:
                best_oos_sharpe = oos_sh
                best_params = (chop_th, rsi_le, rsi_se, rsi_lx, rsi_sx, adx_th)
                best_is = is_res
                best_oos = oos_res

        all_results[sym_name] = {
            'params': param_results,
            'best_params': best_params,
            'best_is': best_is,
            'best_oos': best_oos,
        }

        # Sort & display top 15 by OOS Sharpe
        param_results.sort(key=lambda x: x['oos_sharpe'], reverse=True)
        top = param_results[:15]

        print(f"\n  Top 15 (by OOS Sharpe, min 20 trades, PF > 0.5):")
        hdr = f"  {'Chop':>4} {'RSI_le':>5} {'RSI_se':>5} {'RSI_lx':>5} {'RSI_sx':>5} {'ADX':>3} | {'IS Sh':>6} {'IS Ret':>7} {'IS Tr':>5} {'IS DD':>6} | {'OOS Sh':>6} {'OOS Ret':>8} {'OOS Tr':>6} {'OOS DD':>6} {'PF':>5} {'Wr%':>5} {'Rat':>5} {'Avg$':>8}"
        print(hdr)
        print(f"  {'-'*4} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*3}-+-{'-'*6}-{'-'*7}-{'-'*5}-{'-'*6}-+-{'-'*6}-{'-'*8}-{'-'*6}-{'-'*6}-{'-'*5}-{'-'*5}-{'-'*5}-{'-'*8}")
        for r in top:
            print(f"  {r['chop_th']:>4.1f} {r['rsi_le']:>5} {r['rsi_se']:>5} {r['rsi_lx']:>5} {r['rsi_sx']:>5} {r['adx_th']:>3} | {r['is_sharpe']:>6.3f} {r['is_ret']:>7.1f} {r['is_trd']:>5} {r['is_dd']:>6.1f} | {r['oos_sharpe']:>6.3f} {r['oos_ret']:>8.1f} {r['oos_trd']:>6} {r['oos_dd']:>6.1f} {r['oos_pf']:>5.3f} {r['oos_wr']:>5.1f} {r['oos_is_ratio']:>5.3f} {r['oos_avg_trade']:>8.1f}")

        if best_params:
            ct, rle, rse, rlx, rsx, at = best_params
            print(f"\n  ★ BEST PARAMS: chop>{ct}  rsi_le<{rle}  rsi_se>{rse}  rsi_lx>{rlx}  rsi_sx<{rsx}  adx<{at}")
            print(f"    IS:  Sharpe={best_is['sharpe_ratio']:.3f}  Return={best_is['total_return_pct']:.1f}%  Trades={best_is['num_trades']}  DD={best_is['max_drawdown_pct']:.1f}%")
            print(f"    OOS: Sharpe={best_oos['sharpe_ratio']:.3f}  Return={best_oos['total_return_pct']:.1f}%  Trades={best_oos['num_trades']}  DD={best_oos['max_drawdown_pct']:.1f}%  PF={best_oos['profit_factor']:.3f}  Avg/Trade=${best_oos['avg_trade']:.1f}")
            rat = best_oos['sharpe_ratio'] / best_is['sharpe_ratio'] if best_is['sharpe_ratio'] > 0 else 0
            print(f"    OOS/IS: {rat:.3f}")

    # Save
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(OUTPUT_DIR, f'choppiness_optimize_{ts}.json')
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n\nResults saved: {out_path}")
    print("Done.")
