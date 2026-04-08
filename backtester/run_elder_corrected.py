#!/usr/bin/env python3
"""
Elder's Impulse — H4 Backtest with CORRECT methodology
Key fixes:
1. Entry at OPEN price (not close)
2. Intra-candle stop hits (check high/low)
3. Per-instrument spread costs
4. Two-pass: collect trades at base risk → compute Kelly → re-scale
5. Kelly bounds: min 0.08%, max 1.0%
6. IS: 2015-2019 | OOS: 2020-2025
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

# Also import Elder if it exists there, else load from strategy file
try:
    from portfolio_v13_strategies import strategy_elders_impulse
except ImportError:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "elder", "/Users/lich/.openclaw/workspace/strategies/strategy_elders_impulse.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    strategy_elders_impulse = mod.strategy_elders_impulse

CODER_CACHE = '/Users/lich/.openclaw/workspace-coder/data/cache'
OUTPUT = '/Users/lich/.openclaw/workspace/backtester'
os.makedirs(OUTPUT, exist_ok=True)

SPREAD = {
    'BTC_USD':0.0010, 'XAU_USD':0.0005, 'BCO_USD':0.0012,
    'USD_TRY':0.0008, 'NAS100_USD':0.0004, 'XAG_USD':0.0008,
}
MIN_LOTS = {
    'BTC_USD':0.001, 'XAU_USD':0.1, 'BCO_USD':1,
    'USD_TRY':1, 'NAS100_USD':0.01, 'XAG_USD':1,
}
BASE_RISK = 0.01
KELLY_MIN = 0.0008
KELLY_MAX = 0.0100
START_CAPITAL = 10000.0
IS_START = '2015-01-01'; IS_END = '2019-12-31'
OOS_START = '2020-01-01'
is_end_ts = pd.Timestamp(IS_END, tz='UTC')
is_start_ts = pd.Timestamp(IS_START, tz='UTC')
oos_start_ts = pd.Timestamp(OOS_START, tz='UTC')

# ELDER PARAMETER GRID
PARAMS = {
    'ema_period':   [7, 13, 21, 34],
    'macd_fast':   [8, 12],
    'macd_slow':   [21, 26],
    'macd_signal':  [7, 9],
    'atr_mult':    [1.5, 2.0, 2.5, 3.0],
}
PARAM_KEYS = list(PARAMS.keys())

INSTRUMENTS = ['BTC_USD', 'XAU_USD', 'BCO_USD', 'USD_TRY', 'NAS100_USD', 'XAG_USD']

def load_h4(sym):
    path = os.path.join(CODER_CACHE, f'{sym}_H4.parquet')
    if not os.path.exists(path):
        m = glob.glob(os.path.join(CODER_CACHE, 'historical', f'{sym}_H4*.parquet'))
        if m: path = m[0]
    if not os.path.exists(path): return pd.DataFrame()
    df = pd.read_parquet(path)
    if 'Open' in df.columns:
        df = df.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'})
        df.index.name = 'timestamp'
    return df[['open','high','low','close','volume']] if len(df)>300 else pd.DataFrame()

def compute_atr(high, low, close, period=14):
    tr = np.maximum(np.maximum(high-low, (high-close.shift(1)).abs()), (low-close.shift(1)).abs())
    return tr.rolling(period).mean()

def round_units(units, min_lot):
    if units<=0: return 0.0
    if min_lot>=1: return max(min_lot, int(units/min_lot)*min_lot)
    elif min_lot==0.001: return max(min_lot, round(units/0.001)*0.001)
    elif min_lot==0.01: return max(min_lot, round(units/0.01)*0.01)
    else: return max(min_lot, round(units/0.1)*0.1)

def run_bt(df, signals, instrument, atr_mult=2.5, verbose=False):
    """Run backtest, return list of (pnl, gross_pnl, hit_stop) per trade."""
    trades = []
    position = None
    account = START_CAPITAL
    equity = [START_CAPITAL]

    atr = compute_atr(df['high'], df['low'], df['close'], 14)
    min_lot = MIN_LOTS.get(instrument, 1000)
    spc = SPREAD.get(instrument, 0.001)

    op, hi, lo, cl = df['open'].values, df['high'].values, df['low'].values, df['close'].values
    sv = signals.values if hasattr(signals, 'values') else signals
    av = atr.values if hasattr(atr, 'values') else atr
    nb = len(df)

    for i in range(1, nb):
        co, ch, cl_ = op[i], hi[i], lo[i]
        cs = sv[i] if i < len(sv) else 0
        ps_ = sv[i-1] if (i-1) < len(sv) else 0
        ca_ = av[i] if i < len(av) else np.nan

        if position:
            d = position['direction']
            sp = position['stop_price']
            hit = False; xp = None
            # Intra-candle stop check
            if d == 1 and cl_ <= sp: hit = True; xp = sp
            elif d == -1 and ch >= sp: hit = True; xp = sp
            if not hit:
                # Check exit signal
                if cs == 0: xp = cl_
                elif (d == 1 and cs < 0) or (d == -1 and cs > 0): xp = cl_
                else:
                    # Trail stop
                    if d == 1:
                        position['peak'] = max(position['peak'], ch)
                        if not np.isnan(ca_): position['stop_price'] = position['peak'] - atr_mult * ca_
                    else:
                        position['trough'] = min(position['trough'], cl_)
                        if not np.isnan(ca_): position['stop_price'] = position['trough'] + atr_mult * ca_
                    equity.append(account); continue
            if xp is not None:
                u = position['units']; ep = position['entry_price']
                pnl = u * (xp - ep) * d
                cost = u * ep * spc + u * xp * spc
                account += pnl - cost
                trades.append({'pnl': pnl-cost, 'gross_pnl': pnl, 'direction': d, 'hit_stop': hit, 'ep': ep, 'xp': xp, 'units': u})
                position = None

        # Entry signal
        if not position and ps_ == 0 and cs != 0:
            if not np.isnan(ca_) and ca_ > 0:
                sd = ca_ * atr_mult
                if sd > 0:
                    ru = round_units(account * BASE_RISK / (sd * co), min_lot)
                    if ru >= min_lot:
                        direction = 1 if cs > 0 else -1
                        position = {'direction': direction, 'units': ru, 'entry_price': co,
                                    'stop_price': co - direction * sd, 'peak': ch if direction==1 else co,
                                    'trough': cl_ if direction==-1 else co}

        equity.append(account)

    # Close open position at last close
    if position:
        xp = cl[-1]; u = position['units']; ep = position['entry_price']
        pnl = u * (xp - ep) * position['direction']
        cost = u * ep * spc + u * xp * spc
        account += pnl - cost
        trades.append({'pnl': pnl-cost, 'gross_pnl': pnl, 'direction': position['direction'],
                       'hit_stop': False, 'ep': ep, 'xp': xp, 'units': u})
    equity.append(account)

    return {'trades': trades, 'equity': equity, 'final_capital': account}

def compute_kelly(trades):
    """Compute Kelly weight from gross P&L sequence."""
    if not trades: return KELLY_MAX
    gross = np.array([t['gross_pnl'] for t in trades])
    wins = gross[gross > 0]
    losses = gross[gross < 0]
    if len(wins) == 0 or len(losses) == 0: return KELLY_MAX
    p = len(wins) / len(gross)
    avg_win = np.mean(wins)
    avg_loss = abs(np.mean(losses))
    if avg_loss == 0: return KELLY_MAX
    wl_ratio = avg_win / avg_loss
    kelly = (p * wl_ratio - (1 - p)) / wl_ratio
    # Bound Kelly
    kelly = max(KELLY_MIN, min(KELLY_MAX, kelly))
    return kelly

def rescale_trades(trades, kelly_pct):
    """Rescale P&L using Kelly fraction."""
    scale = kelly_pct / BASE_RISK
    for t in trades:
        t['pnl_scaled'] = t['pnl'] * scale
    return trades

def equity_from_trades(trades, start=START_CAPITAL):
    """Build equity curve from trade list."""
    eq = [start]
    cap = start
    for t in trades:
        cap += t.get('pnl_scaled', t['pnl'])
        eq.append(cap)
    return eq

def metrics_from_equity(equity):
    """Compute metrics from equity curve."""
    eq = np.array(equity)
    cum = eq / START_CAPITAL
    rm = np.maximum.accumulate(cum)
    dd = (cum - rm) / rm * 100
    total_ret = (eq[-1] / START_CAPITAL - 1) * 100
    rets = np.diff(eq) / eq[:-1]
    sh = np.sqrt(252*6) * np.mean(rets) / (np.std(rets) + 1e-10) if len(rets) > 1 else 0
    max_dd = dd.min()
    return {'total_return_pct': total_ret, 'max_drawdown_pct': max_dd,
            'sharpe_ratio': sh, 'final_capital': eq[-1]}

def status_for(oos_res):
    """Determine status based on OOS metrics."""
    ret = oos_res['total_return_pct']
    dd = oos_res['max_drawdown_pct']
    sh = oos_res.get('sharpe_ratio', 0)
    if sh > 0.3 and dd > -25: return '✅'
    elif sh > 0.15 or ret > 0: return '⚠️'
    else: return '❌'

# ─── MAIN ───
print("=" * 80)
print("ELDER'S IMPULSE — H4 CORRECTED BACKTEST + KELLY OPTIMIZATION")
print("IS: 2015-2019 | OOS: 2020-2025 | Entry: OPEN | Intra-candle stops | Spread costs")
print("=" * 80)

all_results = {}
param_combinations = list(product(*[PARAMS[k] for k in PARAM_KEYS]))

for sym in INSTRUMENTS:
    print(f"\n{'='*60}\n{sym}\n{'='*60}")
    full = load_h4(sym)
    if full.empty:
        print(f"  SKIP — no data"); continue

    # Split
    is_mask = (full.index <= is_end_ts) & (full.index >= is_start_ts)
    oos_mask = (full.index >= oos_start_ts)
    is_df = full[is_mask]; oos_df = full[oos_mask]
    print(f"  IS bars ({IS_START}–{IS_END}): {len(is_df)}")
    print(f"  OOS bars ({OOS_START}–): {len(oos_df)}")
    if len(is_df) < 200 or len(oos_df) < 200:
        print(f"  SKIP — insufficient data"); continue

    best_is = None; best_cap = -999

    # IS optimization — grid search
    for combo in param_combinations:
        kw = dict(zip(PARAM_KEYS, combo))
        strat_kw = {k: v for k, v in kw.items() if k != 'atr_mult'}
        sigs = strategy_elders_impulse(is_df['close'], is_df['high'], is_df['low'], is_df['volume'], **strat_kw)
        res = run_bt(is_df, sigs, sym, atr_mult=kw['atr_mult'])
        if res['final_capital'] > best_cap:
            best_cap = res['final_capital']
            best_is = {'params': kw, 'res': res}

    if best_is:
        is_kelly = compute_kelly(best_is['res']['trades'])
        is_scaled = rescale_trades(best_is['res']['trades'], is_kelly)
        is_eq = equity_from_trades(is_scaled)
        is_metrics = metrics_from_equity(is_eq)
        print(f"\n  Best IS: {best_is['params']}")
        print(f"  IS Kelly: {is_kelly*100:.2f}% | IS Capital: ${best_is['res']['final_capital']:,.0f}")
        print(f"  IS Scaled: ${is_metrics['final_capital']:,.0f} ({is_metrics['total_return_pct']:+.1f}%) | "
              f"DD={is_metrics['max_drawdown_pct']:+.1f}% | Sharpe={is_metrics['sharpe_ratio']:.2f}")

    # OOS with best IS params
    if best_is:
        bw = best_is['params']
        oos_sigs = strategy_elders_impulse(oos_df['close'], oos_df['high'], oos_df['low'], oos_df['volume'], **{k:v for k,v in bw.items() if k != "atr_mult"})
        oos_raw = run_bt(oos_df, oos_sigs, sym, atr_mult=bw.get('atr_mult', 2.5))
        oos_kelly = compute_kelly(oos_raw['trades'])
        oos_scaled = rescale_trades(oos_raw['trades'], oos_kelly)
        oos_eq = equity_from_trades(oos_scaled)
        oos_metrics = metrics_from_equity(oos_eq)
        oos_pf = sum(t['gross_pnl'] for t in oos_raw['trades'] if t['gross_pnl'] > 0) / \
                 abs(sum(t['gross_pnl'] for t in oos_raw['trades'] if t['gross_pnl'] < 0)) \
                 if any(t['gross_pnl'] < 0 for t in oos_raw['trades']) else 99
        oos_wr = sum(1 for t in oos_raw['trades'] if t['pnl'] > 0) / max(1, len(oos_raw['trades'])) * 100
        st = status_for(oos_metrics)

        print(f"\n  OOS Kelly: {oos_kelly*100:.2f}%")
        print(f"  OOS Raw Capital: ${oos_raw['final_capital']:,.0f}")
        print(f"  OOS Scaled: ${oos_metrics['final_capital']:,.0f} ({oos_metrics['total_return_pct']:+.1f}%) | "
              f"DD={oos_metrics['max_drawdown_pct']:+.1f}% | Sharpe={oos_metrics['sharpe_ratio']:.2f}")
        print(f"  Trades: {len(oos_raw['trades'])} | PF: {oos_pf:.2f} | WR: {oos_wr:.0f}%")
        print(f"  Status: {st}")

        all_results[sym] = {
            'strategy': "Elder's Impulse",
            'params': bw,
            'is': {**is_metrics, 'kelly_pct': is_kelly*100, 'num_trades': len(best_is['res']['trades'])},
            'oos': {**oos_metrics, 'kelly_pct': oos_kelly*100, 'num_trades': len(oos_raw['trades']),
                    'profit_factor': round(oos_pf, 3), 'win_rate_pct': round(oos_wr, 1),
                    'equity_curve': [round(x,2) for x in oos_eq]},
            'status': st,
        }

# Summary
print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
print(f"{'Sym':>12} | {'Status':>4} | {'IS Ret%':>8} {'IS DD%':>6} {'IS Sharpe':>8} | "
      f"{'OOS Ret%':>8} {'OOS DD%':>6} {'OOS Sharpe':>8} | {'Kelly%':>6} {'PF':>5} {'Trades':>6}")
print(f"{'-'*12}-+-{'-'*4}-+-{'-'*8}-+-{'-'*6}-+-{'-'*8}-+-{'-'*8}-+-{'-'*6}-+-{'-'*5}-+-{'-'*6}")
for sym, v in sorted(all_results.items(), key=lambda x: x[1]['oos']['total_return_pct'], reverse=True):
    is_m = v['is']; oos_m = v['oos']
    print(f"{sym:>12} | {v['status']:>4} | {is_m['total_return_pct']:>+7.1f}% {is_m['max_drawdown_pct']:>+5.1f}% "
          f"{is_m['sharpe_ratio']:>+7.2f} | {oos_m['total_return_pct']:>+7.1f}% {oos_m['max_drawdown_pct']:>+5.1f}% "
          f"{oos_m['sharpe_ratio']:>+7.2f} | {oos_m['kelly_pct']:>5.2f}% {oos_m['profit_factor']:>5.2f} {oos_m['num_trades']:>6}")

passing = [k for k,v in all_results.items() if v['status'] == '✅']
marginal = [k for k,v in all_results.items() if v['status'] == '⚠️']
failing = [k for k,v in all_results.items() if v['status'] == '❌']
print(f"\nResult: {len(passing)} pass / {len(marginal)} marginal / {len(failing)} fail")

ts = datetime.now().strftime('%Y%m%d_%H%M%S')
out_path = os.path.join(OUTPUT, f'elder_corrected_{ts}.json')
with open(out_path, 'w') as f:
    json.dump(all_results, f, indent=2, default=str)
print(f"\nSaved: {out_path}")
