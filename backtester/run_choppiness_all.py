#!/usr/bin/env python3
"""
Choppiness Index MR — ALL INSTRUMENTS Optimizer | Daily
IS: 2015-2019 | OOS: 2020-2025

Instruments: BTC, XAU, XAG, Oil, Brent, NAS100, SP500, DOW, DXY, EURUSD, GBPUSD, USDTRY, ...
Best param from prior runs: chop>50, rsi_le<45, rsi_se>55, rsi_lx>50, rsi_sx<45, adx<25
"""

import sys
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, '/Users/lich/.openclaw/workspace/strategies')
from strategy_choppiness_index_mr import strategy_choppiness_index_mr

try:
    import yfinance as yf
except ImportError:
    print("Install yfinance: pip install yfinance")
    sys.exit(1)

# === ALL INSTRUMENTS ===
INSTRUMENTS = {
    # Crypto
    'BTC_USD': 'BTC-USD',
    'ETH_USD': 'ETH-USD',
    # Commodities
    'XAU_USD': 'GC=F',
    'XAG_USD': 'SI=F',
    'BCO_USD': 'BZ=F',
    'WTI_USD': 'CL=F',
    'NG_USD': 'NG=F',
    'COPPER': 'HG=F',
    # Indices
    'NAS100': 'NQ=F',
    'SP500': 'ES=F',
    'DOW': 'YM=F',
    'RUSSELL': 'RTY=F',
    # Forex / FX
    'DXY': 'DX-Y.NYB',
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'USDJPY=X',
    'USDTRY': 'TRY=X',
    'USDCAD': 'USDCAD=X',
    # Bonds / Rates
    'US10Y': 'TNX',
    # ETFs (as proxies)
    'TLT': 'TLT',
    'GLD': 'GLD',
    'USO': 'USO',
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
    try:
        ticker = yf.Ticker(symbol)
        raw = ticker.history(start=start, end=end, interval='1d')
        if raw.empty or len(raw) < 200:
            return pd.DataFrame()
        raw = raw.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'})
        raw.index.name = 'timestamp'
        return raw[['open','high','low','close','volume']]
    except Exception as e:
        print(f"  ERROR fetching {symbol}: {e}")
        return pd.DataFrame()


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
    position = 0; entry_price = 0.0; shares = 0; entry_idx = 0; margin_deposited = 0.0

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
                           'entry_price': float(entry_price), 'exit_price': float(exit_px),
                           'position': 1, 'pnl': float(pnl)})
            shares = 0; position = 0; entry_price = 0.0; entry_idx = 0
        elif position == -1 and signal != -1:
            exit_px = price * (1 + slippage) * (1 + commission)
            pnl = (entry_price - exit_px) * shares
            cash += pnl
            trades.append({'entry_idx': entry_idx, 'exit_idx': i,
                           'entry_price': float(entry_price), 'exit_price': float(exit_px),
                           'position': -1, 'pnl': float(pnl)})
            shares = 0; position = 0; entry_price = 0.0; margin_deposited = 0.0; entry_idx = 0

        # ENTRY
        if position == 0 and signal != 0:
            available = cash + margin_deposited
            position_value = max(available * 0.95, 0)

            if signal == 1 and position_value > 0:
                entry_px = price * (1 + slippage) * (1 + commission)
                sh = max(int(position_value / entry_px), 0)
                if sh > 0:
                    cash -= sh * entry_px; entry_price = entry_px
                    position = 1; entry_idx = i; shares = sh
            elif signal == -1 and position_value > 0:
                entry_px = price * (1 + slippage) * (1 + commission)
                sh = max(int(position_value / entry_px), 0)
                if sh > 0:
                    margin_deposited = sh * entry_px
                    cash -= margin_deposited; cash += sh * entry_px
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
            cash += pnl; margin_deposited = 0.0
        trades.append({'entry_idx': entry_idx, 'exit_idx': n-1,
                       'entry_price': float(entry_price), 'exit_price': float(exit_px),
                       'position': position, 'pnl': float(pnl)})
        equity_series[-1] = cash + margin_deposited

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
    }


if __name__ == '__main__':
    # Best params from XAU optimization
    chop_th, rsi_le, rsi_se, rsi_lx, rsi_sx, adx_th = 50, 45, 55, 50, 45, 25

    print("="*90)
    print(f"Choppiness Index MR — ALL INSTRUMENTS | Daily | Best Param Set")
    print(f"chop>{chop_th} rsi_le<{rsi_le} rsi_se>{rsi_se} rsi_lx>{rsi_lx} rsi_sx<{rsi_sx} adx<{adx_th}")
    print(f"IS: 2015-2019 | OOS: 2020-2025")
    print("="*90)

    results = {}
    passed = 0
    failed = 0
    skipped = 0

    for sym_name, yf_sym in INSTRUMENTS.items():
        print(f"\n  [{sym_name:10s}] {yf_sym}...", end=' ', flush=True)

        full_data = fetch_daily(yf_sym, IS_START, OOS_END)
        if full_data.empty or len(full_data) < 200:
            print("SKIP (no data / <200 bars)")
            skipped += 1
            continue

        split_idx = full_data.index.searchsorted(OOS_START, side='left')
        is_data = full_data.iloc[:split_idx]
        oos_data = full_data.iloc[split_idx:]

        # Run strategy
        is_signals = strategy_choppiness_index_mr(is_data)
        is_res = run_backtest_fixed(is_data, is_signals)

        oos_signals = strategy_choppiness_index_mr(oos_data)
        oos_res = run_backtest_fixed(oos_data, oos_signals)

        if is_res is None or oos_res is None:
            print("ERROR")
            failed += 1
            continue

        is_sh = is_res['sharpe_ratio']
        oos_sh = oos_res['sharpe_ratio']
        ratio = oos_sh / is_sh if is_sh > 0 else 0

        rec = {
            'symbol': yf_sym,
            'is_bars': is_data.shape[0], 'oos_bars': oos_data.shape[0],
            'is_sharpe': is_sh, 'is_ret': is_res['total_return_pct'],
            'is_trades': is_res['num_trades'], 'is_dd': is_res['max_drawdown_pct'],
            'oos_sharpe': oos_sh, 'oos_ret': oos_res['total_return_pct'],
            'oos_trades': oos_res['num_trades'], 'oos_dd': oos_res['max_drawdown_pct'],
            'oos_pf': oos_res['profit_factor'],
            'oos_wr': oos_res['win_rate_pct'],
            'oos_avg_trade': oos_res['avg_trade'],
            'oos_is_ratio': round(ratio, 3),
            'final_value': oos_res['final_value'],
        }
        results[sym_name] = rec

        # Status flag
        if oos_res['profit_factor'] >= 1.0 and oos_sh > 0.3 and oos_res['max_drawdown_pct'] > -50:
            status = "✅ PASS"
            passed += 1
        elif oos_res['profit_factor'] >= 0.8:
            status = "⚠️ MARGINAL"
            failed += 0
        else:
            status = "❌ FAIL"
            failed += 1

        print(f"{status:12s} IS Sh={is_sh:>6.3f} Ret={is_res['total_return_pct']:>7.1f}% Trd={is_res['num_trades']:>3}  |  OOS Sh={oos_sh:>6.3f} Ret={oos_res['total_return_pct']:>7.1f}% Trd={oos_res['num_trades']:>3} DD={oos_res['max_drawdown_pct']:>6.1f}% PF={oos_res['profit_factor']:>5.3f}")

    # Summary table
    print(f"\n{'='*90}")
    print(f"SUMMARY — {passed} passed / {failed} failed / {skipped} skipped")
    print(f"{'='*90}")
    hdr = f"{'Symbol':>10s} | {'IS Sh':>6} {'IS Ret%':>7} {'IS Tr':>5}  | {'OOS Sh':>6} {'OOS Ret%':>8} {'OOS Tr':>6} {'OOS DD%':>8} {'PF':>5} {'Wr%':>5} {'OOS/IS':>6} {'Status':>10}"
    print(hdr)
    print('-' * len(hdr))

    # Sort by OOS Sharpe
    sorted_results = sorted(results.items(), key=lambda x: x[1]['oos_sharpe'], reverse=True)
    for sym, r in sorted_results:
        if r['oos_pf'] >= 1.0 and r['oos_sharpe'] > 0.3 and r['oos_dd'] > -50:
            status = "✅ PASS"
        elif r['oos_pf'] >= 0.8:
            status = "⚠️ MARGINAL"
        else:
            status = "❌ FAIL"
        print(f"{sym:>10s} | {r['is_sharpe']:>6.3f} {r['is_ret']:>7.1f} {r['is_trades']:>5}  | {r['oos_sharpe']:>6.3f} {r['oos_ret']:>8.1f} {r['oos_trades']:>6} {r['oos_dd']:>8.1f} {r['oos_pf']:>5.3f} {r['oos_wr']:>5.1f} {r['oos_is_ratio']:>6.3f} {status:>10}")

    # Save
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(OUTPUT_DIR, f'choppiness_all_instruments_{ts}.json')
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved: {out_path}")
    print("Done.")
