#!/usr/bin/env python3
"""
Portfolio v13 — H4 Optimization (using coder workspace cached Oanda data)
6 strategies × 6 live instruments | IS: 2015-2019 | OOS: 2020-2025
Kelly/ATR sizing: 2% risk × 0.25 Kelly = 0.5% effective risk per trade
"""

import sys, json, os, glob
from datetime import datetime
from itertools import product
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, '/Users/lich/.openclaw/workspace/strategies')
from portfolio_v13_strategies import (
    strategy_donchian_breakout, strategy_macd_momentum,
    strategy_volatility_expansion, strategy_adx_trend,
    strategy_ichimoku_cloud, strategy_supertrend_vol,
)

INSTRUMENTS = ['BTC_USD', 'XAU_USD', 'BCO_USD', 'USD_TRY', 'NAS100_USD', 'XAG_USD']
CODER_CACHE = '/Users/lich/.openclaw/workspace-coder/data/cache'

IS_START, IS_END = '2015-01-01', '2019-12-31'
OOS_START_VAL, OOS_END = '2020-01-01', '2025-12-31'

COMM = 0.001; SLIP = 0.0005; IC = 100000
OUTPUT = '/Users/lich/.openclaw/workspace/backtester'
os.makedirs(OUTPUT, exist_ok=True)

BARS_PER_YEAR = 252 * 6  # H4 = 6 bars/day

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
    # Try main cache
    path = os.path.join(CODER_CACHE, f'{sym_name}_H4.parquet')
    if not os.path.exists(path):
        # Try historical
        matches = glob.glob(os.path.join(CODER_CACHE, 'historical', f'{sym_name}_H4*.parquet'))
        if matches:
            path = matches[0]
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_parquet(path)
    if 'Open' in df.columns:
        df = df.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'})
        df.index.name = 'timestamp'
    if len(df) < 500:
        return pd.DataFrame()
    return df[['open','high','low','close','volume']]


def _atr_arr(h, l, c, period=14):
    pc = c.shift(1)
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    return tr.rolling(window=period).mean().values


def bt_kelly(data, signals, risk_pct=0.02, kelly_frac=0.25):
    n = len(data)
    if n == 0:
        return None
    ca = data['close'].values
    atr_vals = _atr_arr(pd.Series(data['high'].values, index=data.index),
                        pd.Series(data['low'].values, index=data.index),
                        pd.Series(ca, index=data.index), 14)
    cash = IC
    nav = np.zeros(n)
    trades = []
    pos = 0; ep = 0.0; ei = 0; ps = 0.0

    for i in range(n):
        sig = signals.iloc[i] if i < len(signals) else 0
        px = ca[i]
        c_atr = atr_vals[i] if i < len(atr_vals) else 0
        unreal = ps*(px-ep) if pos==1 else (ps*(ep-px) if pos==-1 else 0.0)
        nav[i] = cash + unreal

        # EXIT
        if pos != 0 and sig != pos:
            if pos == 1:
                xp = px*(1-SLIP)*(1-COMM); pnl = (xp-ep)*ps; cash += xp*ps
            else:
                xp = px*(1+SLIP)*(1+COMM); pnl = (ep-xp)*ps; cash += pnl
            trades.append({'ei':ei,'xi':i,'ep':float(ep),'xp':float(xp),'p':int(pos),'pnl':float(pnl),'sh':float(ps)})
            pos=0; ep=0.0; ps=0.0

        # ENTRY
        if pos == 0 and sig != 0:
            risk_amt = cash * risk_pct * kelly_frac
            sd = c_atr if not np.isnan(c_atr) and c_atr > 0 else px*0.02
            if sd <= 0:
                continue
            ps = risk_amt / sd
            if ps <= 0:
                continue
            if sig == 1:
                epx = px*(1+SLIP)*(1+COMM)
                cost = epx*ps
                if cost > cash*3: ps = (cash*3)/epx; cost = epx*ps
                if ps > 0:
                    cash -= cost; ep = epx; pos = 1; ei = i
            else:
                epx = px*(1+SLIP)*(1+COMM)
                if ps*epx > cash*3: ps = (cash*3)/epx
                ep = epx; pos = -1; ei = i

    # Close remaining
    if pos != 0 and n > 0:
        fp = ca[-1]
        if pos == 1:
            xp = fp*(1-SLIP)*(1-COMM); pnl = (xp-ep)*ps; cash += xp*ps
        else:
            xp = fp*(1+SLIP)*(1+COMM); pnl = (ep-xp)*ps; cash += pnl
        trades.append({'ei':ei,'xi':n-1,'ep':float(ep),'xp':float(xp),'p':int(pos),'pnl':float(pnl),'sh':float(ps)})
        nav[-1] = cash

    tr = len(trades)
    if tr == 0:
        return None
    wins = sum(1 for t in trades if t['pnl'] > 0)
    gp = sum(t['pnl'] for t in trades if t['pnl'] > 0)
    gl = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
    pf = gp/gl if gl > 0 else (float('inf') if gp > 0 else 0)
    rets = pd.Series(nav).pct_change().fillna(0)
    sharpe = np.sqrt(BARS_PER_YEAR)*(rets.mean()/rets.std()) if rets.std()>0 and len(rets)>1 else 0
    cum = (1+rets).cumprod(); rm = cum.expanding().max()
    dd = (cum-rm)/rm; mx_dd = dd.min()*100

    return {'total_return_pct':round((nav[-1]/IC-1)*100,2), 'num_trades':tr,
            'win_rate_pct':round(wins/tr*100,2), 'sharpe_ratio':round(sharpe,3),
            'max_drawdown_pct':round(mx_dd,2), 'profit_factor':round(pf,3),
            'final_value':round(nav[-1],2)}


if __name__ == '__main__':
    risk_pct = 0.02; kelly_frac = 0.25
    eff = risk_pct * kelly_frac

    print("="*100)
    print(f"Portfolio v13 — H4 Optimization (Oanda cached data)")
    print(f"IS: 2015-2019 | OOS: 2020-2025 | Risk: {eff*100}% per trade")
    print(f"Instruments: {', '.join(INSTRUMENTS)}")
    print("="*100)

    all_results = {}
    inst_count = len(INSTRUMENTS)

    for idx, sym in enumerate(INSTRUMENTS, 1):
        print(f"\n[{idx}/{inst_count}] {sym}")
        full = load_h4(sym)
        if full.empty or len(full) < 500:
            print("  SKIP"); continue
        split = full.index.searchsorted(OOS_START_VAL, side='left')
        is_d, oos_d = full.iloc[:split], full.iloc[split:]
        print(f"  H4 bars: IS={is_d.shape[0]} OOS={oos_d.shape[0]} ({full.index[0].date()} → {full.index[-1].date()})")

        for stk, st_label, grid in STRATEGIES:
            keys = STRAT_KEYS[stk]
            combos = list(product(*[grid[k] for k in keys]))
            st_fn = STRAT_FN[stk]

            best_oos_sh = -999; best_p = None; best_is = None; best_oos = None

            for combo in combos:
                kw = dict(zip(keys, combo))
                s1 = st_fn(is_d['close'], is_d['high'], is_d['low'], is_d['volume'], **kw)
                r1 = bt_kelly(is_d, s1, risk_pct, kelly_frac)
                if r1 is None or r1['num_trades'] < 10:
                    continue
                s2 = st_fn(oos_d['close'], oos_d['high'], oos_d['low'], oos_d['volume'], **kw)
                r2 = bt_kelly(oos_d, s2, risk_pct, kelly_frac)
                if r2 is None:
                    continue
                if r2['sharpe_ratio'] > best_oos_sh and r2['num_trades'] >= 10:
                    best_oos_sh = r2['sharpe_ratio']
                    best_p = combo; best_is = r1; best_oos = r2

            if best_p:
                ratio = best_oos['sharpe_ratio']/best_is['sharpe_ratio'] if best_is['sharpe_ratio']>0 else 0
                pf = best_oos['profit_factor']
                if pf >= 1.0 and best_oos['sharpe_ratio'] > 0.3 and best_oos['max_drawdown_pct'] > -30:
                    status = "✅"
                elif best_oos['sharpe_ratio'] > 0.3 and best_oos['max_drawdown_pct'] > -50:
                    status = "⚠️"
                else:
                    status = "❌"
                ps = ' | '.join(f'{k}={v}' for k,v in zip(keys, best_p))
                print(f"    [{stk:12s}] {status} Sh={best_oos['sharpe_ratio']:>6.3f} Ret={best_oos['total_return_pct']:>7.1f}% Tr={best_oos['num_trades']:>5} DD={best_oos['max_drawdown_pct']:>6.1f}% PF={best_oos['profit_factor']:>5.3f} | {ps}")
                all_results[f"{sym}_{stk}"] = {
                    'strategy': st_label, 'params': dict(zip(keys, best_p)),
                    'is': best_is, 'oos': best_oos, 'oos_is_ratio': round(ratio,3), 'status': status,
                }
            else:
                print(f"    [{stk:12s}] -- No valid params (<10 trades)")

    # Summary
    print(f"\n{'='*100}")
    passing = [k for k,v in all_results.items() if v['status']=='✅']
    marginal = [k for k,v in all_results.items() if v['status']=='⚠️']
    failing = [k for k,v in all_results.items() if v['status']=='❌']
    print(f"SUMMARY: {len(passing)} pass / {len(marginal)} marginal / {len(failing)} fail / {len(passing)+len(marginal)+len(failing)} total")

    sorted_res = sorted(all_results.items(), key=lambda x: x[1]['oos']['sharpe_ratio'], reverse=True)
    hdr = f"{'Key':>30s} | {'Strategy':>20s} | {'IS Sh':>6} {'IS Ret':>7} {'IS DD':>6} {'IS Tr':>5} | {'OOS Sh':>6} {'OOS Ret':>7} {'OOS DD':>6} {'OOS Tr':>5} {'PF':>5} {'Wr%':>5} {'Status':>8}"
    print(f"\n{hdr}")
    print('-'*len(hdr))
    for k, v in sorted_res:
        o = v['oos']; i = v['is']
        print(f"{k:>30s} | {v['strategy']:>20s} | {i['sharpe_ratio']:>6.3f} {i['total_return_pct']:>6.1f}% {i['max_drawdown_pct']:>5.1f}% {i['num_trades']:>5} | {o['sharpe_ratio']:>6.3f} {o['total_return_pct']:>6.1f}% {o['max_drawdown_pct']:>5.1f}% {o['num_trades']:>5} {o['profit_factor']:>5.3f} {o['win_rate_pct']:>5.1f} {v['status']:>8}")

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = os.path.join(OUTPUT, f'portfolio_v13_h4_kelly_{ts}.json')
    with open(out, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nSaved: {out}")
    print("Done.")
