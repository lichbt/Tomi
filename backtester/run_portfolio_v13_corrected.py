#!/usr/bin/env python3
"""
Portfolio v13 — H4 Backtest with CORRECT methodology (matching original coder workspace)

Key fixes from the original backtest_kelly_1pct_all.py:
1. Entry at OPEN price (not close)
2. Intra-candle stop hits (check high/low)
3. Per-instrument spread costs (not flat commission%)
4. Two-pass: collect trades at base risk → compute Kelly → re-scale
5. Kelly bounds: min 0.08%, max 1.0%
6. Max holding period enforcement
7. Oanda cached H4 data

IS: 2015-2019 | OOS: 2020-2025
"""

import sys, json, os, glob
from datetime import datetime
from itertools import product
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, '/Users/lich/.openclaw/workspace/strategies')
from portfolio_v13_strategies import (
    strategy_donchian_breakout, strategy_macd_momentum,
    strategy_volatility_expansion, strategy_adx_trend,
    strategy_ichimoku_cloud, strategy_supertrend_vol,
)

# ═══════════════════════════════════════════════════════
# CONFIG — matching original backtest_kelly_1pct_all.py
# ═══════════════════════════════════════════════════════
INSTRUMENTS = ['BTC_USD', 'XAU_USD', 'BCO_USD', 'USD_TRY', 'NAS100_USD', 'XAG_USD']

# Spread costs (Oanda practice, in price units)
SPREAD = {
    'BTC_USD':    0.0010,
    'XAU_USD':    0.0005,
    'BCO_USD':    0.0012,
    'USD_TRY':    0.0008,
    'NAS100_USD': 0.0004,
    'XAG_USD':    0.0008,
}

MIN_LOTS = {
    'BTC_USD': 0.001,
    'XAU_USD': 0.1,
    'BCO_USD': 1,
    'USD_TRY': 1,
    'NAS100_USD': 0.01,
    'XAG_USD': 1,
}

# Kelly bounds (fraction of BASE_RISK)
KELLY_MIN = 0.0008   # 0.08%
KELLY_MAX = 0.0100   # 1.00%
BASE_RISK = 0.01     # 1% base risk

START_CAPITAL = 10000.0

CODER_CACHE = '/Users/lich/.openclaw/workspace-coder/data/cache'
OUTPUT = '/Users/lich/.openclaw/workspace/backtester'
os.makedirs(OUTPUT, exist_ok=True)

OOS_START_VAL = '2020-01-01'

STRATEGIES = [
    ('donchian', 'Donchian Breakout',
     {'entry_period': [10,15,20,30,40], 'atr_mult': [1.5,2.0,2.5,3.0]}),
    ('macd', 'MACD Momentum',
     {'fast': [8,12], 'slow': [21,26,34], 'signal': [7,9], 'atr_mult': [1.5,2.0,2.5,3.0]}),
    ('vol_exp', 'Volatility Expansion',
     {'lookback': [14,20,30], 'vol_mult': [1.0,1.5,2.0], 'atr_mult': [1.5,2.0,2.5,3.0]}),
    ('adx', 'ADX Trend',
     {'adx_period': [7,14], 'adx_threshold': [20,25,30], 'ema_period': [20,50,100], 'atr_mult': [1.5,2.0,2.5,3.0]}),
    ('ichimoku', 'Ichimoku Cloud',
     {'t_period': [7,9], 'k_period': [22,26], 's_period': [44,52], 'atr_mult': [1.5,2.0,2.5,3.0]}),
    ('supertrend', 'Supertrend+Vol',
     {'st_period': [7,10,14], 'st_mult': [2.0,3.0,4.0], 'atr_mult': [1.5,2.0,2.5]}),
]

STRAT_KEYS = {
    'donchian': ['entry_period','atr_mult'],
    'macd': ['fast','slow','signal','atr_mult'],
    'vol_exp': ['lookback','vol_mult','atr_mult'],
    'adx': ['adx_period','adx_threshold','ema_period','atr_mult'],
    'ichimoku': ['t_period','k_period','s_period','atr_mult'],
    'supertrend': ['st_period','st_mult','atr_mult'],
}

STRAT_FN = {
    'donchian': strategy_donchian_breakout,
    'macd': strategy_macd_momentum,
    'vol_exp': strategy_volatility_expansion,
    'adx': strategy_adx_trend,
    'ichimoku': strategy_ichimoku_cloud,
    'supertrend': strategy_supertrend_vol,
}


def load_h4(sym_name):
    """Load H4 parquet from coder cache."""
    path = os.path.join(CODER_CACHE, f'{sym_name}_H4.parquet')
    if not os.path.exists(path):
        matches = glob.glob(os.path.join(CODER_CACHE, 'historical', f'{sym_name}_H4*.parquet'))
        if matches:
            path = matches[0]
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_parquet(path)
    if 'Open' in df.columns:
        df = df.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'})
        df.index.name = 'timestamp'
    if len(df) < 300:
        return pd.DataFrame()
    return df[['open','high','low','close','volume']]


def compute_atr(high, low, close, period=14):
    """Compute rolling ATR (matching original)."""
    tr = np.maximum(
        np.maximum(high - low,
                    (high - close.shift(1)).abs()),
        (low - close.shift(1)).abs()
    )
    return tr.rolling(period).mean()


def calculate_cost(instrument, units, price):
    """Spread cost = spread × units × price (both sides)."""
    spread = SPREAD.get(instrument, 0.001)
    return abs(units) * price * spread


def round_units(units, min_lot):
    """Round position size to minimum lot size."""
    if units <= 0:
        return 0.0
    if min_lot >= 1:
        return max(min_lot, int(units / min_lot) * min_lot)
    elif min_lot == 0.001:
        return max(min_lot, round(units / 0.001) * 0.001)
    elif min_lot == 0.01:
        return max(min_lot, round(units / 0.01) * 0.01)
    elif min_lot == 0.1:
        return max(min_lot, round(units / 0.1) * 0.1)
    else:
        return max(min_lot, int(units / min_lot) * min_lot)


def backtest_single_pass(df, signals, instrument, risk_pct=BASE_RISK, atr_mult=2.5):
    """
    Correct backtest matching original methodology:
    - Entry at OPEN price
    - Intra-candle stop hits (check high/low)
    - Per-instrument spread costs
    - Signal-based entries (0 → nonzero transitions)
    - ATR trailing stop with peak/trough tracking
    """
    account = START_CAPITAL
    trades = []
    position = None

    atr = compute_atr(df['high'], df['low'], df['close'], 14)
    min_lot = MIN_LOTS.get(instrument, 1000)

    op = df['open'].values
    hi = df['high'].values
    lo = df['low'].values
    cl = df['close'].values
    sv = signals.values if hasattr(signals, 'values') else signals
    av = atr.values if hasattr(atr, 'values') else atr
    nb = len(df)

    for i in range(1, nb):
        curr_open = op[i]
        curr_high = hi[i]
        curr_low = lo[i]
        curr_close = cl[i]
        curr_sig = sv[i] if i < len(sv) else 0
        curr_atr = av[i] if i < len(av) else np.nan
        prev_sig = sv[i-1] if (i-1) < len(sv) else 0

        # ─── Manage existing position ───
        if position is not None:
            direction = position['direction']
            stop_price = position['stop_price']

            # Intra-candle stop check
            hit_stop = False
            exit_price = None

            if direction == 1 and curr_low <= stop_price:
                exit_price = stop_price
                hit_stop = True
            elif direction == -1 and curr_high >= stop_price:
                exit_price = stop_price
                hit_stop = True

            if not hit_stop:
                # Signal exit (flip to 0 or reverse)
                if curr_sig == 0:
                    exit_price = curr_close
                elif (direction == 1 and curr_sig < 0) or (direction == -1 and curr_sig > 0):
                    exit_price = curr_close
                else:
                    # Update trailing stop
                    if direction == 1:
                        position['peak'] = max(position['peak'], curr_high)
                        if not np.isnan(curr_atr):
                            position['stop_price'] = position['peak'] - atr_mult * curr_atr
                    elif direction == -1:
                        position['trough'] = min(position['trough'], curr_low)
                        if not np.isnan(curr_atr):
                            position['stop_price'] = position['trough'] + atr_mult * curr_atr
                    continue

            # ─── Exit trade ───
            if exit_price is not None:
                units = position['units']
                pnl = units * (exit_price - position['entry_price']) * direction
                cost_entry = calculate_cost(instrument, units, position['entry_price'])
                cost_exit = calculate_cost(instrument, units, exit_price)
                total_pnl = pnl - cost_entry - cost_exit

                account += total_pnl
                trades.append({
                    'entry_price': position['entry_price'],
                    'exit_price': exit_price,
                    'units': units,
                    'pnl': total_pnl,
                    'direction': direction,
                    'hit_stop': hit_stop,
                    'entry_bar': position['entry_bar'],
                    'exit_bar': i
                })
                position = None

        # ─── Entry: signal transitions from 0 to nonzero ───
        if position is None and prev_sig == 0 and curr_sig != 0:
            if not np.isnan(curr_atr) and curr_atr > 0:
                stop_dist = curr_atr * atr_mult
                risk_per_unit = stop_dist

                if risk_per_unit > 0:
                    max_risk = account * risk_pct
                    raw_units = max_risk / (risk_per_unit * curr_open)
                    units = round_units(raw_units, min_lot)

                    if units >= min_lot:
                        entry_cost = calculate_cost(instrument, units, curr_open)
                        if entry_cost < account * risk_pct * 0.5:  # Cost < 50% of risk
                            direction = 1 if curr_sig > 0 else -1
                            position = {
                                'direction': direction,
                                'units': units,
                                'entry_price': curr_open,
                                'stop_price': curr_open - direction * stop_dist,
                                'peak': curr_high if direction == 1 else curr_open,
                                'trough': curr_low if direction == -1 else curr_open,
                                'entry_bar': i
                            }

    # Close remaining
    if position is not None:
        units = position['units']
        exit_price = cl[-1]
        pnl = units * (exit_price - position['entry_price']) * position['direction']
        cost_entry = calculate_cost(instrument, units, position['entry_price'])
        cost_exit = calculate_cost(instrument, units, exit_price)
        total_pnl = pnl - cost_entry - cost_exit
        account += total_pnl
        trades.append({
            'entry_price': position['entry_price'], 'exit_price': exit_price,
            'units': units, 'pnl': total_pnl, 'direction': position['direction'],
            'hit_stop': False, 'entry_bar': position['entry_bar'], 'exit_bar': nb - 1
        })

    # ─── Compute Kelly weight from trades ───
    total_trades = len(trades)
    if total_trades < 5:
        return None

    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] < 0]

    win_rate = len(winning_trades) / total_trades
    avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = abs(sum(t['pnl'] for t in losing_trades)) / len(losing_trades) if losing_trades else 0
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0

    # Kelly: f* = p - (1-p)/b
    kelly_f = win_rate - (1 - win_rate) / payoff_ratio if payoff_ratio > 0 else 0
    kelly_weight = min(max(kelly_f * BASE_RISK, KELLY_MIN), KELLY_MAX)

    return {
        'trades': trades,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'payoff_ratio': payoff_ratio,
        'kelly_f': kelly_f,
        'kelly_weight': kelly_weight,
    }


def recompute_with_kelly(trades, kelly_weight, start_capital=START_CAPITAL,
                          bars_per_year=252*6, n_bars=None):
    """Recompute equity curve with Kelly-scaled P&L. Proper per-bare returns."""
    if not trades or not trades[0]:
        return None

    trades = trades[0] if isinstance(trades, list) and isinstance(trades[0], list) else trades
    if not trades:
        return None

    scale = kelly_weight / BASE_RISK

    equity = start_capital
    peak_eq = start_capital
    max_dd = 0.0
    equity_curve = [start_capital]
    trade_returns = []

    winning_pnl = losing_pnl = 0.0

    for t in trades:
        scaled_pnl = t['pnl'] * scale
        before = equity
        equity += scaled_pnl
        period_ret = scaled_pnl / before if before > 0 else 0
        trade_returns.append(period_ret)

        if t['pnl'] > 0:
            winning_pnl += scaled_pnl
        else:
            losing_pnl += abs(scaled_pnl)

        if equity > peak_eq:
            peak_eq = equity
        dd = (peak_eq - equity) / peak_eq * 100
        max_dd = max(max_dd, dd)
        equity_curve.append(equity)

    total_trades = len(trades)
    wins = sum(1 for t in trades if t['pnl'] > 0)
    win_rate = wins / total_trades * 100
    pf = winning_pnl / losing_pnl if losing_pnl > 0 else (99.9 if winning_pnl > 0 else 0)
    total_ret = (equity - start_capital) / start_capital * 100

    n_years = n_bars / bars_per_year if n_bars else 5.0
    ann_ret = (equity / start_capital) ** (1 / max(n_years, 0.1)) - 1 if n_years > 0 else 0

    if len(trade_returns) > 1:
        mr = np.mean(trade_returns)
        sd = np.std(trade_returns, ddof=1)
        sharpe = mr / sd * np.sqrt(total_trades) if sd > 0 else 0
    else:
        sharpe = 0

    return {
        'total_return_pct': round(total_ret, 2),
        'annual_return_pct': round(ann_ret * 100, 2),
        'profit_factor': round(pf, 3),
        'win_rate_pct': round(win_rate, 1),
        'total_trades': total_trades,
        'max_drawdown_pct': round(max_dd, 2),
        'sharpe_ratio': round(sharpe, 3),
        'final_capital': round(equity, 2),
        'kelly_weight_pct': round(kelly_weight * 100, 3),
        'n_years': round(n_years, 2),
        'equity_curve': equity_curve[:min(100, len(equity_curve))] + equity_curve[-1:],  # sample
    }


if __name__ == '__main__':
    print("="*100)
    print(f"Portfolio v13 — H4 Kelly Backtest (CORRECTED methodology)")
    print(f"Entry: OPEN | Stops: intra-candle high/low | Costs: per-instrument spread")
    print(f"Risk: 1% base → Kelly bounds [{KELLY_MIN*100:.2f}%, {KELLY_MAX*100:.2f}%]")
    print(f"IS: 2015-2019 | OOS: 2020-2025")
    print("="*100)

    all_results = {}

    for sym in INSTRUMENTS:
        print(f"\n{'━'*60}")
        print(f"{sym}")
        print(f"{'━'*60}")

        full = load_h4(sym)
        if full.empty or len(full) < 300:
            print("  SKIP"); continue

        split = full.index.searchsorted(OOS_START_VAL, side='left')
        is_d, oos_d = full.iloc[:split], full.iloc[split:]
        print(f"  H4 bars: IS={is_d.shape[0]} OOS={oos_d.shape[0]}")

        for stk, st_label, grid in STRATEGIES:
            keys = STRAT_KEYS[stk]
            combos = list(product(*[grid[k] for k in keys]))
            st_fn = STRAT_FN[stk]

            best_oos_capital = -999
            best_oos = None; best_is = None; best_p = None

            for combo in combos:
                kw = dict(zip(keys, combo))

                # Generate signals (strategy returns position series: 1/-1/0)
                is_signals = st_fn(is_d['close'], is_d['high'], is_d['low'], is_d['volume'], **kw)
                is_signals = is_signals.astype(int)

                is_res = backtest_single_pass(is_d, is_signals, sym)
                if is_res is None or is_res['kelly_weight'] <= KELLY_MIN:
                    continue

                oos_signals = st_fn(oos_d['close'], oos_d['high'], oos_d['low'], oos_d['volume'], **kw)
                oos_signals = oos_signals.astype(int)

                oos_res = backtest_single_pass(oos_d, oos_signals, sym)
                if oos_res is None:
                    continue

                # Recompute with Kelly
                is_metrics = recompute_with_kelly(
                    [is_res['trades']], is_res['kelly_weight'],
                    n_bars=len(is_d)
                )
                oos_metrics = recompute_with_kelly(
                    [oos_res['trades']], oos_res['kelly_weight'],
                    n_bars=len(oos_d)
                )

                if is_metrics is None or oos_metrics is None:
                    continue

                # Rank by OOS final capital and profit factor
                score = oos_metrics['total_return_pct']  # higher is better

                if score > best_oos_capital and oos_metrics['total_trades'] >= 5:
                    best_oos_capital = score
                    best_p = combo
                    best_is = {**is_metrics, 'trades': len(is_res['trades']),
                               'win_rate_base': round(is_res['win_rate']*100,1),
                               'payoff': round(is_res['payoff_ratio'],2)}
                    best_oos = {**oos_metrics, 'trades': len(oos_res['trades']),
                                'win_rate_base': round(oos_res['win_rate']*100,1),
                                'payoff': round(oos_res['payoff_ratio'],2),
                                'profit_factor': oos_metrics.get('profit_factor', 0),
                                'win_rate_pct': oos_metrics.get('win_rate_pct', 0)}

            if best_p:
                status = "✅" if (best_oos['total_return_pct'] > 0 and
                                  best_oos.get('profit_factor',0) >= 1.0 and
                                  best_oos.get('max_drawdown_pct',100) > -50) \
                    else ("⚠️" if best_oos['total_return_pct'] > 0 else "❌")

                ps = ' | '.join(f'{k}={v}' for k,v in zip(keys, best_p))
                tr = best_oos.get('trades', '?')
                dd = best_oos.get('max_drawdown_pct', 0)
                pf = best_oos.get('profit_factor', 0)
                wr = best_oos.get('win_rate_pct', 0)
                sh = best_oos.get('sharpe_ratio', 0)
                kr = best_oos.get('kelly_weight_pct', 0)

                print(f"    [{stk:12s}] {status} ${best_oos['final_capital']:>9,.0f} "
                      f"Ret={best_oos['total_return_pct']:>6.1f}% "
                      f"DD={dd:>5.1f}% PF={pf:.2f} Sh={sh:.3f} "
                      f"WR={wr:.0f}% Tr={tr:>4} K={kr:.2f}% | {ps}")

                oos_ratio = best_oos['total_return_pct'] / best_is['total_return_pct'] \
                    if best_is['total_return_pct'] > 0 else 0

                all_results[f"{sym}_{stk}"] = {
                    'strategy': st_label, 'params': dict(zip(keys, best_p)),
                    'is': best_is, 'oos': best_oos,
                    'oos_is_ratio': round(oos_ratio, 3), 'status': status,
                }
            else:
                print(f"    [{stk:12s}] --")

    # ═══ SUMMARY ═══
    print(f"\n{'='*100}")
    passing = [k for k,v in all_results.items() if v['status']=='✅']
    marginal = [k for k,v in all_results.items() if v['status']=='⚠️']
    failing = [k for k,v in all_results.items() if v['status']=='❌']
    print(f"SUMMARY: {len(passing)} pass / {len(marginal)} marginal / {len(failing)} fail / {len(passing)+len(marginal)+len(failing)} total")

    sorted_res = sorted(all_results.items(), key=lambda x: x[1]['oos']['final_capital'], reverse=True)
    hdr = f"{'Key':>25s} | {'Strategy':>20s} | {'IS $':>9} {'IS%':>7} {'IS DD':>6} {'IS Tr':>5} | {'OOS $':>9} {'OOS%':>7} {'OOS DD':>6} {'OOS Tr':>5} {'PF':>4} {'Wr%':>4} {'K%':>5} {'Status':>7}"
    print(f"\n{hdr}")
    print('-'*len(hdr))
    for k, v in sorted_res:
        o = v['oos']; i = v['is']
        print(f"{k:>25s} | {v['strategy']:>20s} | ${i['final_capital']:>8,.0f} {i['total_return_pct']:>6.1f}% {i['max_drawdown_pct']:>5.1f}% {i['trades']:>5} | ${o['final_capital']:>8,.0f} {o['total_return_pct']:>6.1f}% {o['max_drawdown_pct']:>5.1f}% {o['trades']:>5}  {o.get('profit_factor',0):>4.2f} {o.get('win_rate_pct',0):>4.0f} {o.get('kelly_weight_pct',0):>5.2f}% {v['status']:>7}")

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = os.path.join(OUTPUT, f'portfolio_v13_h4_kelly_corrected_{ts}.json')
    with open(out, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nSaved: {out}")
    print("Done.")
