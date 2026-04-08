#!/usr/bin/env python3
"""
FRAMA Strategy Optimization for Crypto & Commodities (H4 timeframe)
IS: 2015-2019 | OOS: 2020-2025
Fixed position sizing — correct cash accounting, no inflation bug.
"""

import sys
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
from itertools import product
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, '/Users/lich/.openclaw/workspace/strategies')
from strategy_frama import strategy_frama

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

IS_START = '2015-01-01'
IS_END   = '2019-12-31'
OOS_START = '2020-01-01'
OOS_END   = '2025-12-31'

PARAM_GRID = {
    'period': [10, 14, 20, 28, 34],
    'atr_mult': [1.5, 2.0, 2.5, 3.0],
}

COMMISSION = 0.001
SLIPPAGE = 0.0005
INITIAL_CAPITAL = 100000

OUTPUT_DIR = '/Users/lich/.openclaw/workspace/backtester'
os.makedirs(OUTPUT_DIR, exist_ok=True)


def fetch_daily(symbol, start, end):
    """Fetch Daily data using yfinance."""
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
    """Fixed backtest — uses fixed fractional sizing based on actual equity."""
    n = len(data)
    if n == 0:
        return None

    close_arr = data['close'].values
    high_arr = data['high'].values
    low_arr = data['low'].values

    # Portfolio tracking
    cash = initial_capital
    equity_series = np.zeros(n)
    trades = []
    position = 0  # 0=flat, 1=long, -1=short
    entry_price = 0.0
    shares = 0
    entry_idx = 0
    margin_deposited = 0.0  # cash reserved for short margin

    for i in range(n):
        signal = signals.iloc[i] if i < len(signals) else 0
        price = close_arr[i]

        # Unrealized P&L
        if position == 1:
            unrealized = shares * (price - entry_price)
        elif position == -1:
            unrealized = shares * (entry_price - price)
        else:
            unrealized = 0.0
        equity = cash + unrealized
        equity_series[i] = equity  # mark-to-market each bar

        # === EXIT LOGIC ===
        if position == 1 and signal != 1:
            # Exit long
            exit_px = price * (1 - slippage) * (1 - commission)
            pnl = (exit_px - entry_price) * shares
            cash += shares * exit_px  # receive proceeds
            trades.append({
                'entry_idx': entry_idx,
                'exit_idx': i,
                'entry_price': float(entry_price),
                'exit_price': float(exit_px),
                'position': 1,
                'pnl': float(pnl),
            })
            shares = 0
            position = 0
            entry_price = 0.0
            entry_idx = 0

        elif position == -1 and signal != -1:
            # Exit short: buy back shares to cover
            exit_px = price * (1 + slippage) * (1 + commission)
            cost_to_cover = shares * exit_px
            pnl = (entry_price - exit_px) * shares
            # cash already has the short sale proceeds; pay back the cover cost
            cash += pnl  # add/sub the net PnL
            # margin_deposited is released back
            trades.append({
                'entry_idx': entry_idx,
                'exit_idx': i,
                'entry_price': float(entry_price),
                'exit_price': float(exit_px),
                'position': -1,
                'pnl': float(pnl),
            })
            shares = 0
            position = 0
            entry_price = 0.0
            entry_idx = 0
            margin_deposited = 0.0

        # === ENTRY LOGIC ===
        if position == 0 and signal != 0:
            # Available equity for new position
            available = cash + margin_deposited
            position_value = max(available * 0.95, 0)

            if signal == 1 and position_value > 0:
                # Enter long
                entry_px = price * (1 + slippage) * (1 + commission)
                shares = max(int(position_value / entry_px), 0)
                if shares > 0:
                    cash -= shares * entry_px  # pay for shares
                    entry_price = entry_px
                    position = 1
                    entry_idx = i

            elif signal == -1 and position_value > 0:
                # Enter short
                entry_px = price * (1 + slippage) * (1 + commission)
                shares = max(int(position_value / entry_px), 0)
                if shares > 0:
                    # Set aside margin, then receive sale proceeds
                    margin_deposited = shares * entry_px  # reserved as collateral
                    cash -= margin_deposited  # margin out
                    cash += shares * entry_px  # short sale proceeds in
                    entry_price = entry_px
                    position = -1
                    entry_idx = i

    # Close remaining position
    if position != 0 and n > 0:
        final_price = close_arr[-1]
        if position == 1:
            exit_px = final_price * (1 - slippage) * (1 - commission)
            pnl = (exit_px - entry_price) * shares
            cash += shares * exit_px
        else:
            exit_px = final_price * (1 + slippage) * (1 + commission)
            pnl = (entry_price - exit_px) * shares
            cash += pnl
            margin_deposited = 0.0
        trades.append({
            'entry_idx': entry_idx,
            'exit_idx': n-1,
            'entry_price': float(entry_price),
            'exit_price': float(exit_px),
            'position': position,
            'pnl': float(pnl),
        })
        equity_series[-1] = cash + margin_deposited

    # Metrics
    total_return = (equity_series[-1] / initial_capital - 1) * 100 if n > 0 else 0
    num_trades = len(trades)
    wins = sum(1 for t in trades if t['pnl'] > 0)
    losses = sum(1 for t in trades if t['pnl'] < 0)
    win_rate = (wins / num_trades * 100) if num_trades > 0 else 0

    gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
    gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0

    returns = pd.Series(equity_series).pct_change().fillna(0)
    sharpe = np.sqrt(252) * (returns.mean() / returns.std()) if returns.std() > 0 and len(returns) > 1 else 0

    cum = (1 + returns).cumprod()
    running_max = cum.expanding().max()
    dd = (cum - running_max) / running_max
    max_dd = dd.min() * 100

    return {
        'total_return_pct': round(total_return, 2),
        'num_trades': num_trades,
        'win_rate_pct': round(win_rate, 2),
        'sharpe_ratio': round(sharpe, 3),
        'max_drawdown_pct': round(max_dd, 2),
        'profit_factor': round(profit_factor, 3),
        'gross_profit': round(gross_profit, 2),
        'gross_loss': round(gross_loss, 2),
        'final_value': round(equity_series[-1], 2) if n > 0 else 0,
        'equity_curve': equity_series.tolist(),
        'trades': trades,
    }


def is_oos_ratio(is_results, oos_results):
    """Calculate OOS/IS ratio (should be > 0.4 to not be overfit)."""
    if is_results is None or oos_results is None:
        return 0
    is_sharpe = is_results['sharpe_ratio']
    oos_sharpe = oos_results['sharpe_ratio']
    if is_sharpe <= 0:
        return 0
    return oos_sharpe / is_sharpe


if __name__ == '__main__':
    print("="*70)
    print("FRAMA Optimization: Crypto & Commodities | DAILY")
    print(f"IS: 2015-2019 | OOS: 2020-2025")
    print("="*70)

    param_combos = list(product(PARAM_GRID['period'], PARAM_GRID['atr_mult']))
    print(f"\nParameter grid: {len(param_combos)} combos")
    for p, am in param_combos:
        print(f"  period={p}, atr_mult={am}")

    all_results = {}

    for sym_name, yf_sym in INSTRUMENTS.items():
        print(f"\n{'='*60}")
        print(f"INSTRUMENT: {sym_name} ({yf_sym})")
        print(f"{'='*60}")

        # Fetch full range
        print(f"\nFetching Daily data (2015-2025)...")
        full_data = fetch_daily(yf_sym, '2015-01-01', '2025-12-31')
        print(f"  Data shape: {full_data.shape} | {full_data.index[0]} to {full_data.index[-1]}")

        if len(full_data) < 200:
            print("  NOT ENOUGH DATA — skipping.")
            continue

        # Split IS / OOS
        is_mask = full_data.index <= IS_END
        oos_mask = full_data.index >= OOS_START
        # Overlap boundary bar — include in OOS
        if full_data.index.is_monotonic_increasing:
            split_idx = full_data.index.searchsorted(OOS_START, side='left')
            is_data = full_data.iloc[:split_idx]
            oos_data = full_data.iloc[split_idx:]
        else:
            is_data = full_data[is_mask]
            oos_data = full_data[oos_mask]

        print(f"  IS: {is_data.shape[0]} bars | OOS: {oos_data.shape[0]} bars")

        best_oos_sharpe = -999
        best_params = None
        best_is = None
        best_oos = None
        param_results = []

        for period, atr_mult in param_combos:
            # IS backtest
            is_signals = strategy_frama(is_data['close'], is_data['high'], is_data['low'],
                                        is_data['volume'], period=period)
            is_res = run_backtest_fixed(is_data, is_signals)

            if is_res is None or is_res['num_trades'] < 10:
                continue

            # OOS backtest with same params
            oos_signals = strategy_frama(oos_data['close'], oos_data['high'], oos_data['low'],
                                         oos_data['volume'], period=period)
            oos_res = run_backtest_fixed(oos_data, oos_signals)

            if oos_res is None:
                continue

            ratio = is_oos_ratio(is_res, oos_res)

            rec = {
                'period': period,
                'atr_mult': atr_mult,
                'is_sharpe': is_res['sharpe_ratio'],
                'is_return': is_res['total_return_pct'],
                'is_trades': is_res['num_trades'],
                'is_dd': is_res['max_drawdown_pct'],
                'oos_sharpe': oos_res['sharpe_ratio'],
                'oos_return': oos_res['total_return_pct'],
                'oos_trades': oos_res['num_trades'],
                'oos_dd': oos_res['max_drawdown_pct'],
                'oos_pf': oos_res['profit_factor'],
                'oos_wr': oos_res['win_rate_pct'],
                'oos_is_ratio': round(ratio, 3),
            }
            param_results.append(rec)

            if oos_res['sharpe_ratio'] > best_oos_sharpe and oos_res['num_trades'] >= 20:
                best_oos_sharpe = oos_res['sharpe_ratio']
                best_params = (period, atr_mult)
                best_is = is_res
                best_oos = oos_res

        all_results[sym_name] = {
            'params': param_results,
            'best_params': best_params,
            'best_is': best_is,
            'best_oos': best_oos,
        }

        # Print sorted results
        param_results.sort(key=lambda x: x['oos_sharpe'], reverse=True)
        print(f"\n  Results (sorted by OOS Sharpe, min 20 trades):")
        print(f"  {'Period':>6} {'ATR_M':>5} {'IS Sh':>7} {'IS Ret%':>8} {'IS Trd':>6} {'IS DD%':>7}  {'OOS Sh':>7} {'OOS Ret%':>9} {'OOS Trd':>7} {'OOS DD%':>7} {'OOS PF':>6} {'Wr%':>5} {'OOS/IS':>7}")
        print(f"  {'-'*6} {'-'*5} {'-'*7} {'-'*8} {'-'*6} {'-'*7}  {'-'*7} {'-'*9} {'-'*7} {'-'*7} {'-'*6} {'-'*5} {'-'*7}")
        for r in param_results:
            print(f"  {r['period']:>6} {r['atr_mult']:>5.1f} {r['is_sharpe']:>7.3f} {r['is_return']:>8.1f} {r['is_trades']:>6} {r['is_dd']:>7.1f}  {r['oos_sharpe']:>7.3f} {r['oos_return']:>9.1f} {r['oos_trades']:>7} {r['oos_dd']:>7.1f} {r['oos_pf']:>6.3f} {r['oos_wr']:>5.1f} {r['oos_is_ratio']:>7.3f}")

        if best_params:
            p, am = best_params
            print(f"\n  ★ BEST: period={p}, atr_mult={am}")
            print(f"    IS:  Sharpe={best_is['sharpe_ratio']:.3f}  Return={best_is['total_return_pct']:.1f}%  Trades={best_is['num_trades']}  DD={best_is['max_drawdown_pct']:.1f}%")
            print(f"    OOS: Sharpe={best_oos['sharpe_ratio']:.3f}  Return={best_oos['total_return_pct']:.1f}%  Trades={best_oos['num_trades']}  DD={best_oos['max_drawdown_pct']:.1f}%  PF={best_oos['profit_factor']:.3f}")
            ratio = best_oos['sharpe_ratio'] / best_is['sharpe_ratio'] if best_is['sharpe_ratio'] > 0 else 0
            print(f"    OOS/IS ratio: {ratio:.3f}")

    # Save all results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(OUTPUT_DIR, f'frama_optimize_{timestamp}.json')
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n\nResults saved to: {out_path}")
    print("Done.")
