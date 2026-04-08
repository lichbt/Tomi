#!/usr/bin/env python3
"""
Elder's Impulse System — ALL INSTRUMENTS Optimizer | Daily
IS: 2015-2019 | OOS: 2020-2025
Param grid: ema_period, atr_mult (trailing stop)
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
from strategy_elders_impulse import strategy_elders_impulse

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
    # Forex
    'DXY': 'DX-Y.NYB',
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'USDJPY=X',
    'USDTRY': 'TRY=X',
    'USDCAD': 'USDCAD=X',
    # ETFs
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
    try:
        ticker = yf.Ticker(symbol)
        raw = ticker.history(start=start, end=end, interval='1d')
        if raw.empty or len(raw) < 200:
            return pd.DataFrame()
        raw = raw.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'})
        raw.index.name = 'timestamp'
        return raw[['open','high','low','close','volume']]
    except Exception:
        return pd.DataFrame()


def run_backtest_fixed(data, signals, initial_capital=INITIAL_CAPITAL,
                       commission=COMMISSION, slippage=SLIPPAGE):
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
    # Param grid
    param_grid = list(product(
        [7, 10, 13, 20, 34],   # ema_period
        [1.5, 2.0, 2.5, 3.0],  # atr_mult (trailing stop)
    ))
    print(f"Parameter grid: {len(param_grid)} combos")

    all_results = {}
    n_instruments = len(INSTRUMENTS)
    cur = 0

    for sym_name, yf_sym in INSTRUMENTS.items():
        cur += 1
        print(f"\n[{cur}/{n_instruments}] {sym_name:10s} ({yf_sym})")

        full_data = fetch_daily(yf_sym, IS_START, OOS_END)
        if full_data.empty or len(full_data) < 200:
            print(f"  SKIP (no data)")
            continue

        print(f"  Data: {full_data.shape[0]} bars ({full_data.index[0].date()} → {full_data.index[-1].date()})")

        split_idx = full_data.index.searchsorted(OOS_START, side='left')
        is_data = full_data.iloc[:split_idx]
        oos_data = full_data.iloc[split_idx:]
        print(f"  IS: {is_data.shape[0]} bars | OOS: {oos_data.shape[0]} bars")

        best_oos_sharpe = -999
        best_params = None
        best_is = None
        best_oos = None
        param_results = []

        for ema_period, atr_mult in param_grid:
            # Modify strategy to use custom atr_mult
            # We need a wrapper since strategy_elders_impulse hardcodes 2.5x ATR
            close = is_data['close']
            high = is_data['high']
            low = is_data['low']
            volume = is_data['volume']
            n = len(close)
            min_bars = max(ema_period, 26) + 9 + 2
            if n < min_bars:
                continue

            ema = close.ewm(span=ema_period, adjust=False).mean()
            ema_fast = close.ewm(span=12, adjust=False).mean()
            ema_slow = close.ewm(span=26, adjust=False).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            histogram = macd_line - signal_line

            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.ewm(span=14, adjust=False).mean()

            ema_up = ema > ema.shift(1)
            ema_down = ema < ema.shift(1)
            hist_rising = histogram > histogram.shift(1)
            hist_falling = histogram < histogram.shift(1)

            impulse_long = ema_up & hist_rising
            impulse_short = ema_down & hist_falling
            exit_long = hist_falling | ema_down
            exit_short = hist_rising | ema_up

            signals = np.zeros(n, dtype=int)
            pos_val = 0; ep = 0.0; e_idx = 0
            long_stop = 0.0; short_stop = 0.0; e_atr = 0.0

            for i in range(n):
                if np.isnan(close.values[i]) or np.isnan(atr.values[i]):
                    continue

                price = close.values[i]
                cur_atr = atr.values[i]

                # trailing stop check
                if pos_val == 1 and long_stop > 0 and price < long_stop:
                    pos_val = 0; ep = 0.0; long_stop = 0.0
                    signals[i] = 0; continue
                if pos_val == -1 and short_stop > 0 and price > short_stop:
                    pos_val = 0; ep = 0.0; short_stop = 0.0
                    signals[i] = 0; continue

                if pos_val == 1:
                    if exit_long.values[i]: pos_val = 0; ep = 0.0; long_stop = 0.0; signals[i] = 0
                    else: signals[i] = 1
                    continue
                if pos_val == -1:
                    if exit_short.values[i]: pos_val = 0; ep = 0.0; short_stop = 0.0; signals[i] = 0
                    else: signals[i] = -1
                    continue

                if impulse_long.values[i]:
                    pos_val = 1; ep = price; e_atr = cur_atr if not np.isnan(cur_atr) else 0
                    long_stop = ep - atr_mult * e_atr
                    signals[i] = 1
                elif impulse_short.values[i]:
                    pos_val = -1; ep = price; e_atr = cur_atr if not np.isnan(cur_atr) else 0
                    short_stop = ep + atr_mult * e_atr
                    signals[i] = -1
                else:
                    signals[i] = 0

            is_signals = pd.Series(signals, index=is_data.index)
            is_res = run_backtest_fixed(is_data, is_signals)
            if is_res is None or is_res['num_trades'] < 10:
                continue

            # OOS
            close_o = oos_data['close']
            high_o = oos_data['high']
            low_o = oos_data['low']
            volume_o = oos_data['volume']
            no = len(close_o)
            if no < min_bars:
                continue

            ema_o = close_o.ewm(span=ema_period, adjust=False).mean()
            ema_fast_o = close_o.ewm(span=12, adjust=False).mean()
            ema_slow_o = close_o.ewm(span=26, adjust=False).mean()
            macd_line_o = ema_fast_o - ema_slow_o
            signal_line_o = macd_line_o.ewm(span=9, adjust=False).mean()
            histogram_o = macd_line_o - signal_line_o

            tr1_o = high_o - low_o
            tr2_o = (high_o - close_o.shift(1)).abs()
            tr3_o = (low_o - close_o.shift(1)).abs()
            tr_o = pd.concat([tr1_o, tr2_o, tr3_o], axis=1).max(axis=1)
            atr_o = tr_o.ewm(span=14, adjust=False).mean()

            ema_up_o = ema_o > ema_o.shift(1)
            ema_down_o = ema_o < ema_o.shift(1)
            hist_rising_o = histogram_o > histogram_o.shift(1)
            hist_falling_o = histogram_o < histogram_o.shift(1)

            impulse_long_o = ema_up_o & hist_rising_o
            impulse_short_o = ema_down_o & hist_falling_o
            exit_long_o = hist_falling_o | ema_down_o
            exit_short_o = hist_rising_o | ema_up_o

            signals_o = np.zeros(no, dtype=int)
            pos_val_o = 0; ep_o = 0.0; e_idx_o = 0
            long_stop_o = 0.0; short_stop_o = 0.0; e_atr_o = 0.0

            for i in range(no):
                if np.isnan(close_o.values[i]) or np.isnan(atr_o.values[i]):
                    continue
                price = close_o.values[i]
                cur_atr = atr_o.values[i]
                if pos_val_o == 1 and long_stop_o > 0 and price < long_stop_o:
                    pos_val_o = 0; ep_o = 0.0; long_stop_o = 0.0
                    signals_o[i] = 0; continue
                if pos_val_o == -1 and short_stop_o > 0 and price > short_stop_o:
                    pos_val_o = 0; ep_o = 0.0; short_stop_o = 0.0
                    signals_o[i] = 0; continue
                if pos_val_o == 1:
                    if exit_long_o.values[i]:
                        pos_val_o = 0; ep_o = 0.0; long_stop_o = 0.0; signals_o[i] = 0
                    else: signals_o[i] = 1
                    continue
                if pos_val_o == -1:
                    if exit_short_o.values[i]:
                        pos_val_o = 0; ep_o = 0.0; short_stop_o = 0.0; signals_o[i] = 0
                    else: signals_o[i] = -1
                    continue
                if impulse_long_o.values[i]:
                    pos_val_o = 1; ep_o = price; e_atr_o = cur_atr if not np.isnan(cur_atr) else 0
                    long_stop_o = ep_o - atr_mult * e_atr_o
                    signals_o[i] = 1
                elif impulse_short_o.values[i]:
                    pos_val_o = -1; ep_o = price; e_atr_o = cur_atr if not np.isnan(cur_atr) else 0
                    short_stop_o = ep_o + atr_mult * e_atr_o
                    signals_o[i] = -1
                else:
                    signals_o[i] = 0

            oos_signals = pd.Series(signals_o, index=oos_data.index)
            oos_res = run_backtest_fixed(oos_data, oos_signals)
            if oos_res is None:
                continue

            is_sh = is_res['sharpe_ratio']
            oos_sh = oos_res['sharpe_ratio']
            ratio = oos_sh / is_sh if is_sh > 0 else 0

            rec = {
                'ema_period': ema_period, 'atr_mult': atr_mult,
                'is_sharpe': round(is_sh, 3), 'is_ret': is_res['total_return_pct'],
                'is_trd': is_res['num_trades'], 'is_dd': is_res['max_drawdown_pct'],
                'oos_sharpe': round(oos_sh, 3), 'oos_ret': oos_res['total_return_pct'],
                'oos_trd': oos_res['num_trades'], 'oos_dd': oos_res['max_drawdown_pct'],
                'oos_pf': oos_res['profit_factor'],
                'oos_wr': oos_res['win_rate_pct'],
                'oos_is_ratio': round(ratio, 3),
                'oos_avg_trade': oos_res['avg_trade'],
                'oos_final': oos_res['final_value'],
            }
            param_results.append(rec)

            if oos_sh > best_oos_sharpe and oos_res['num_trades'] >= 20:
                best_oos_sharpe = oos_sh
                best_params = (ema_period, atr_mult)
                best_is = is_res
                best_oos = oos_res

        all_results[sym_name] = {
            'params': param_results,
            'best_params': best_params,
            'best_is': best_is,
            'best_oos': best_oos,
        }

        if best_params:
            ep, am = best_params
            print(f"  ★ BEST: ema={ep} atr_mult={am}")
            print(f"    IS:  Sh={best_is['sharpe_ratio']:.3f} Ret={best_is['total_return_pct']:.1f}% Trd={best_is['num_trades']} DD={best_is['max_drawdown_pct']:.1f}%")
            print(f"    OOS: Sh={best_oos['sharpe_ratio']:.3f} Ret={best_oos['total_return_pct']:.1f}% Trd={best_oos['num_trades']} DD={best_oos['max_drawdown_pct']:.1f}% PF={best_oos['profit_factor']:.3f} Avg/Trd=${best_oos['avg_trade']:.0f}")
            ratio = best_oos['sharpe_ratio'] / best_is['sharpe_ratio'] if best_is['sharpe_ratio'] > 0 else 0
            print(f"    OOS/IS: {ratio:.3f}")
        else:
            print(f"  ⚠️ No params passed filter")

    # Summary table
    print(f"\n{'='*100}")
    print(f"SUMMARY — BEST PARAMS PER INSTRUMENT")
    print(f"{'='*100}")
    hdr = f"{'Symbol':>10s} | {'EMA':>3} {'ATR':>3} | {'IS Sh':>6} {'IS Ret%':>8} {'IS Tr':>5} {'IS DD%':>7} | {'OOS Sh':>6} {'OOS Ret%':>8} {'OOS Tr':>6} {'OOS DD%':>7} {'PF':>5} {'Wr%':>5} {'Avg$':>8} {'Status':>10}"
    print(hdr)
    print('-' * len(hdr))

    all_by_sharpe = []
    for sym, d in all_results.items():
        if d['best_oos'] is None:
            continue
        bp = d['best_params']
        bo = d['best_oos']
        bi = d['best_is']
        ratio = bo['sharpe_ratio'] / bi['sharpe_ratio'] if bi['sharpe_ratio'] > 0 else 0

        if bo['profit_factor'] >= 1.0 and bo['sharpe_ratio'] > 0.3 and bo['max_drawdown_pct'] > -50:
            status = "✅ PASS"
        elif bo['profit_factor'] >= 0.8 and bo['profit_factor'] <= 1.0:
            status = "⚠️ MARGINAL"
        elif bo['sharpe_ratio'] > 0.3:
            status = "⚠️ MARGINAL"
        else:
            status = "❌ FAIL"

        all_by_sharpe.append((sym, bp, bi, bo, bo['sharpe_ratio'], status, ratio))

    all_by_sharpe.sort(key=lambda x: x[4], reverse=True)

    passed_count = sum(1 for x in all_by_sharpe if 'PASS' in x[5])
    failed_count = sum(1 for x in all_by_sharpe if 'FAIL' in x[5])
    marginal_count = sum(1 for x in all_by_sharpe if 'MARGINAL' in x[5])
    print(f"\n  {passed_count} passed / {marginal_count} marginal / {failed_count} failed\n")

    for sym, bp, bi, bo, sh, status, ratio in all_by_sharpe:
        ep_str = str(bp[0]) if bp else '-'
        am_str = f"{bp[1]:.1f}" if bp else '-'
        print(f"{sym:>10s} | {ep_str:>3} {am_str:>3} | {bi['sharpe_ratio']:>6.3f} {bi['total_return_pct']:>8.1f} {bi['num_trades']:>5} {bi['max_drawdown_pct']:>7.1f} | {bo['sharpe_ratio']:>6.3f} {bo['total_return_pct']:>8.1f} {bo['num_trades']:>6} {bo['max_drawdown_pct']:>7.1f} {bo['profit_factor']:>5.3f} {bo['win_rate_pct']:>5.1f} {bo['avg_trade']:>8.0f} {status:>10}")

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(OUTPUT_DIR, f'elder_impulse_optimize_daily_{ts}.json')
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved: {out_path}")
    print("Done.")
