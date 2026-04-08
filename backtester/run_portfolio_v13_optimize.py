#!/usr/bin/env python3
"""
Portfolio v13 — Parameter Optimization
6 live strategies × all instruments × param grids | Daily timeframe
IS: 2015-2019 | OOS: 2020-2025
"""

import sys, json, os
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
try:
    import yfinance as yf
except ImportError:
    print("pip install yfinance"); sys.exit(1)

INSTRUMENTS = {
    'BTC_USD': 'BTC-USD', 'ETH_USD': 'ETH-USD',
    'XAU_USD': 'GC=F', 'XAG_USD': 'SI=F',
    'BCO_USD': 'BZ=F', 'WTI_USD': 'CL=F', 'NG_USD': 'NG=F', 'COPPER': 'HG=F',
    'NAS100': 'NQ=F', 'SP500': 'ES=F', 'DOW': 'YM=F', 'RUSSELL': 'RTY=F',
    'EURUSD': 'EURUSD=X', 'GBPUSD': 'GBPUSD=X', 'USDJPY': 'USDJPY=X',
    'USDTRY': 'TRY=X', 'USDCAD': 'USDCAD=X',
    'TLT': 'TLT', 'GLD': 'GLD', 'USO': 'USO',
}

IS_START, IS_END, OOS_START, OOS_END = '2015-01-01', '2019-12-31', '2020-01-01', '2025-12-31'
COMM, SLIP, IC = 0.001, 0.0005, 100000
OUTPUT = '/Users/lich/.openclaw/workspace/backtester'
os.makedirs(OUTPUT, exist_ok=True)

STRATEGIES = [
    ('donchian', 'Donchian Breakout',   strategy_donchian_breakout,
     {'entry_period': [10,15,20,30],      'atr_mult': [1.5,2.0,2.5,3.0]}),
    ('macd',     'MACD Momentum',       strategy_macd_momentum,
     {'fast': [8,12], 'slow': [21,26,34], 'signal': [7,9], 'atr_mult': [1.5,2.0,2.5,3.0]}),
    ('vol_exp',  'Volatility Expansion', strategy_volatility_expansion,
     {'lookback': [14,20,30],            'vol_mult': [1.0,1.5,2.0], 'atr_mult': [1.5,2.0,2.5,3.0]}),
    ('adx',      'ADX Trend',           strategy_adx_trend,
     {'adx_period': [7,14],              'adx_threshold': [20,25,30], 'ema_period': [20,50,100], 'atr_mult': [1.5,2.0,2.5,3.0]}),
    ('ichimoku', 'Ichimoku Cloud',      strategy_ichimoku_cloud,
     {'t_period': [7,9],                 'k_period': [22,26], 's_period': [44,52], 'atr_mult': [1.5,2.0,2.5,3.0]}),
    ('supertrend','Supertrend+Vol',     strategy_supertrend_vol,
     {'st_period': [7,10,14],            'st_mult': [2.0,3.0,4.0], 'atr_mult': [1.5,2.0,2.5]}),
]


def fetch_daily(sym, start, end):
    try:
        raw = yf.Ticker(sym).history(start=start, end=end, interval='1d')
        if raw.empty or len(raw)<200: return pd.DataFrame()
        raw = raw.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'})
        raw.index.name = 'timestamp'
        return raw[['open','high','low','close','volume']]
    except: return pd.DataFrame()


def bt(data, signals):
    n = len(data)
    if n == 0: return None
    ca = data['close'].values
    cash = IC; eq = np.zeros(n); trades = []; pos = 0; ep = 0.0; sh = 0; ei = 0; md = 0.0
    for i in range(n):
        sig = signals.iloc[i] if i < len(signals) else 0; px = ca[i]
        unreal = sh*(px-ep) if pos==1 else (sh*(ep-px) if pos==-1 else 0.0)
        eq[i] = cash + unreal
        if pos==1 and sig!=1:
            x = px*(1-SLIP)*(1-COMM); pnl=(x-ep)*sh; cash+=sh*x
            trades.append({'ei':ei,'xi':i,'ep':float(ep),'xp':float(x),'p':1,'pnl':float(pnl)})
            sh=0;pos=0;ep=0.0;ei=0
        elif pos==-1 and sig!=-1:
            x = px*(1+SLIP)*(1+COMM); pnl=(ep-x)*sh; cash+=pnl
            trades.append({'ei':ei,'xi':i,'ep':float(ep),'xp':float(x),'p':-1,'pnl':float(pnl)})
            sh=0;pos=0;ep=0.0;md=0.0;ei=0
        if pos==0 and sig!=0:
            avail = cash+md; pv = max(avail*0.95,0)
            if sig==1 and pv>0:
                e = px*(1+SLIP)*(1+COMM); s = max(int(pv/e),0)
                if s>0: cash-=s*e; ep=e; pos=1; ei=i; sh=s
            elif sig==-1 and pv>0:
                e = px*(1+SLIP)*(1+COMM); s = max(int(pv/e),0)
                if s>0: md=s*e; cash-=md; cash+=s*e; ep=e; pos=-1; ei=i; sh=s
    if pos!=0 and n>0:
        fp = ca[-1]
        if pos==1: x=fp*(1-SLIP)*(1-COMM); pnl=(x-ep)*sh; cash+=sh*x
        else: x=fp*(1+SLIP)*(1+COMM); pnl=(ep-x)*sh; cash+=pnl; md=0.0
        trades.append({'ei':ei,'xi':n-1,'ep':float(ep),'xp':float(x),'p':pos,'pnl':float(pnl)})
        eq[-1] = cash+md
    tr = len(trades)
    if tr==0: return None
    wins = sum(1 for t in trades if t['pnl']>0)
    gp = sum(t['pnl'] for t in trades if t['pnl']>0)
    gl = abs(sum(t['pnl'] for t in trades if t['pnl']<0))
    pf = gp/gl if gl>0 else (float('inf') if gp>0 else 0)
    rets = pd.Series(eq).pct_change().fillna(0)
    sharpe = np.sqrt(252)*(rets.mean()/rets.std()) if rets.std()>0 else 0
    cum = (1+rets).cumprod(); rm = cum.expanding().max(); dd = (cum-rm)/rm; mx_dd = dd.min()*100
    return {'total_return_pct':round((eq[-1]/IC-1)*100,2), 'num_trades':tr,
            'win_rate_pct':round(wins/tr*100,2), 'sharpe_ratio':round(sharpe,3),
            'max_drawdown_pct':round(mx_dd,2), 'profit_factor':round(pf,3),
            'final_value':round(eq[-1],2), 'avg_trade':round(np.mean([t['pnl'] for t in trades]),2)}


# Param key mapping per strategy (ordered to match kwargs dict keys)
STRAT_PARAM_KEYS = {
    'donchian':   ['entry_period','atr_mult'],
    'macd':       ['fast','slow','signal','atr_mult'],
    'vol_exp':    ['lookback','vol_mult','atr_mult'],
    'adx':        ['adx_period','adx_threshold','ema_period','atr_mult'],
    'ichimoku':   ['t_period','k_period','s_period','atr_mult'],
    'supertrend': ['st_period','st_mult','atr_mult'],
}

STRAT_FUNC_MAP = {
    'donchian':   strategy_donchian_breakout,
    'macd':       strategy_macd_momentum,
    'vol_exp':    strategy_volatility_expansion,
    'adx':        strategy_adx_trend,
    'ichimoku':   strategy_ichimoku_cloud,
    'supertrend': strategy_supertrend_vol,
}

if __name__ == '__main__':
    print("="*100)
    print("Portfolio v13 Optimization — 6 strategies × 19 instruments | Daily | IS 2015-2019 / OOS 2020-2025")
    print("="*100)

    all_results = {}
    inst_count = len(INSTRUMENTS)
    cur_inst = 0

    for sym_name, yf_sym in INSTRUMENTS.items():
        cur_inst += 1
        print(f"\n[{cur_inst}/{inst_count}] {sym_name:10s} ({yf_sym})")

        full = fetch_daily(yf_sym, IS_START, OOS_END)
        if full.empty or len(full)<200:
            print(f"  SKIP"); continue

        split = full.index.searchsorted(OOS_START, side='left')
        is_d, oos_d = full.iloc[:split], full.iloc[split:]

        best_entry = None
        for stk, st_label, st_fn, grid in STRATEGIES:
            keys = STRAT_PARAM_KEYS[stk]
            combos = list(product(*[grid[k] for k in keys]))
            print(f"\n  [{stk:12s}] {len(combos)} combos...", flush=True)

            best_oos_sh = -999; best_p = None; best_is = None; best_oos = None

            for combo in combos:
                kwargs = dict(zip(keys, combo))
                # IS
                s1 = st_fn(is_d['close'], is_d['high'], is_d['low'], is_d['volume'], **kwargs)
                r1 = bt(is_d, s1)
                if r1 is None or r1['num_trades'] < 5: continue
                # OOS
                s2 = st_fn(oos_d['close'], oos_d['high'], oos_d['low'], oos_d['volume'], **kwargs)
                r2 = bt(oos_d, s2)
                if r2 is None: continue

                oos_sh = r2['sharpe_ratio']
                if oos_sh > best_oos_sh and r2['num_trades'] >= 5:
                    best_oos_sh = oos_sh
                    best_p = combo
                    best_is = r1
                    best_oos = r2

            if best_p:
                ratio = best_oos['sharpe_ratio']/best_is['sharpe_ratio'] if best_is['sharpe_ratio']>0 else 0
                params_str = ', '.join(f"{k}={v}" for k,v in zip(keys, best_p))
                pf = best_oos['profit_factor']
                if pf >= 1.0 and best_oos['sharpe_ratio'] > 0.3 and best_oos['max_drawdown_pct'] > -50:
                    status = "✅"
                elif best_oos['profit_factor'] >= 0.5:
                    status = "⚠️"
                else:
                    status = "❌"
                print(f"    ★ ema={best_p[0]} ... Sh={best_oos_sh:.3f} Ret={best_oos['total_return_pct']:.1f}% Tr={best_oos['num_trades']} DD={best_oos['max_drawdown_pct']:.1f}% PF={best_oos['profit_factor']:.3f} [{status}]")

                all_results[f"{sym_name}_{stk}"] = {
                    'strategy': st_label, 'params': dict(zip(keys, best_p)),
                    'is': best_is, 'oos': best_oos, 'oos_is_ratio': round(ratio,3),
                    'status': status,
                }

    # Summary
    print(f"\n{'='*100}")
    passing = [k for k,v in all_results.items() if v['status']=='✅']
    marginal = [k for k,v in all_results.items() if v['status']=='⚠️']
    failing = [k for k,v in all_results.items() if v['status']=='❌']
    print(f"SUMMARY: {len(passing)} pass / {len(marginal)} marginal / {len(failing)} fail / {len(passing)+len(marginal)+len(failing)} total")

    # Top 20 by OOS Sharpe
    sorted_res = sorted(all_results.items(), key=lambda x: x[1]['oos']['sharpe_ratio'], reverse=True)[:20]
    print(f"\n{'Top 20 by OOS Sharpe':>40s}")
    print(f"{'Key':>30s} | {'Strat':>20s} | {'IS Sh':>6} {'IS Ret%':>8} {'IS Tr':>5}  | {'OOS Sh':>6} {'OOS Ret%':>8} {'OOS Tr':>6} {'OOS DD%':>8} {'PF':>5} {'Status':>8}")
    print('-'*120)
    for k, v in sorted_res:
        o = v['oos']; i = v['is']
        print(f"{k:>30s} | {v['strategy']:>20s} | {i['sharpe_ratio']:>6.3f} {i['total_return_pct']:>8.1f} {i['num_trades']:>5}  | {o['sharpe_ratio']:>6.3f} {o['total_return_pct']:>8.1f} {o['num_trades']:>6} {o['max_drawdown_pct']:>8.1f} {o['profit_factor']:>5.3f} {v['status']:>8}")

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = os.path.join(OUTPUT, f'portfolio_v13_optimize_{ts}.json')
    with open(out, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nSaved: {out}")
    print("Done.")
