#!/usr/bin/env python3
"""Full optimization: 6 strategies x 2 timeframes (H4 + Daily) with corrected methodology."""
import sys, json, os, glob
from datetime import datetime
from itertools import product
import numpy as np
import pandas as pd
import warnings, importlib.util
warnings.filterwarnings('ignore')

sys.path.insert(0, '/Users/lich/.openclaw/workspace/strategies')
from portfolio_v13_strategies import (
    strategy_donchian_breakout, strategy_macd_momentum,
    strategy_volatility_expansion, strategy_adx_trend,
    strategy_ichimoku_cloud, strategy_supertrend_vol,
)
spec = importlib.util.spec_from_file_location("elder",
    "/Users/lich/.openclaw/workspace/strategies/strategy_elders_impulse.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
strategy_elders_impulse = mod.strategy_elders_impulse

CODER_CACHE = '/Users/lich/.openclaw/workspace-coder/data/cache'
OUTPUT = '/Users/lich/.openclaw/workspace/backtester'
os.makedirs(OUTPUT, exist_ok=True)

SPREAD = {'BTC_USD':0.0010,'XAU_USD':0.0005,'BCO_USD':0.0012,'USD_TRY':0.0008,'NAS100_USD':0.0004,'XAG_USD':0.0008}
MIN_LOTS = {'BTC_USD':0.001,'XAU_USD':0.1,'BCO_USD':1,'USD_TRY':1,'NAS100_USD':0.01,'XAG_USD':1}
BASE_RISK = 0.01; KELLY_MIN = 0.0008; KELLY_MAX = 0.0100; START_CAPITAL = 10000.0
IS_END = pd.Timestamp('2019-12-31', tz='UTC')
IS_START = pd.Timestamp('2015-01-01', tz='UTC')
OOS_START = pd.Timestamp('2020-01-01', tz='UTC')
INSTRUMENTS = ['BTC_USD','XAU_USD','BCO_USD','USD_TRY','NAS100_USD','XAG_USD']

# All strategies with their grids
STRATEGIES = {
    'elder_impulse': {
        'fn': strategy_elders_impulse,
        'params': {
            'ema_period': [7, 13, 21, 34],
            'macd_fast': [8, 12],
            'macd_slow': [21, 26],
            'macd_signal': [7, 9],
            'atr_mult': [1.5, 2.0, 2.5, 3.0],
        },
        'strat_keys': ['ema_period','macd_fast','macd_slow','macd_signal'],
        'atr_key': 'atr_mult',
        'filter_atr': True,
    },
    'volatility_expansion': {
        'fn': strategy_volatility_expansion,
        'params': {
            'lookback': [14, 20, 30],
            'vol_mult': [1.0, 1.5, 2.0],
            'atr_mult': [1.5, 2.0, 2.5, 3.0],
        },
        'strat_keys': ['lookback','vol_mult'],
        'atr_key': 'atr_mult',
        'filter_atr': True,
    },
    'macd_momentum': {
        'fn': strategy_macd_momentum,
        'params': {
            'fast': [8, 12],
            'slow': [21, 26, 34],
            'signal': [7, 9],
            'atr_mult': [1.5, 2.0, 2.5, 3.0],
        },
        'strat_keys': ['fast','slow','signal'],
        'atr_key': 'atr_mult',
        'filter_atr': True,
    },
    'adx_trend': {
        'fn': strategy_adx_trend,
        'params': {
            'adx_period': [7, 14],
            'adx_threshold': [20, 25, 30],
            'ema_period': [20, 50, 100],
            'atr_mult': [1.5, 2.0, 2.5, 3.0],
        },
        'strat_keys': ['adx_period','adx_threshold','ema_period'],
        'atr_key': 'atr_mult',
        'filter_atr': True,
    },
    'ichimoku_cloud': {
        'fn': strategy_ichimoku_cloud,
        'params': {
            't_period': [7, 9],
            'k_period': [22, 26],
            's_period': [44, 52],
            'atr_mult': [1.5, 2.0, 2.5, 3.0],
        },
        'strat_keys': ['t_period','k_period','s_period'],
        'atr_key': 'atr_mult',
        'filter_atr': True,
    },
    'supertrend_vol': {
        'fn': strategy_supertrend_vol,
        'params': {
            'st_period': [7, 10, 14],
            'st_mult': [2.0, 3.0, 4.0],
            'atr_mult': [1.5, 2.0, 2.5],
        },
        'strat_keys': ['st_period','st_mult'],
        'atr_key': 'atr_mult',
        'filter_atr': True,
    },
}

def load_data(sym, tf):
    suffix = 'H4' if tf == 'H4' else 'D'
    path = os.path.join(CODER_CACHE, f'{sym}_{suffix}.parquet')
    if not os.path.exists(path):
        m = glob.glob(os.path.join(CODER_CACHE, 'historical', f'{sym}_{suffix}*.parquet'))
        if m: path = m[0]
    if not os.path.exists(path): return pd.DataFrame()
    df = pd.read_parquet(path)
    if 'Open' in df.columns:
        df = df.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'})
        df.index.name = 'timestamp'
    return df[['open','high','low','close','volume']] if len(df)>100 else pd.DataFrame()

def compute_atr(high, low, close, period=14):
    tr = np.maximum(np.maximum(high-low, (high-close.shift(1)).abs()), (low-close.shift(1)).abs())
    return tr.rolling(period).mean()

def round_units(units, min_lot):
    if units<=0: return 0.0
    if min_lot>=1: return max(min_lot, int(units/min_lot)*min_lot)
    elif min_lot==0.001: return max(min_lot, round(units/0.001)*0.001)
    elif min_lot==0.01: return max(min_lot, round(units/0.01)*0.01)
    else: return max(min_lot, round(units/0.1)*0.1)

def run_bt(df, signals, instrument, atr_mult=2.5):
    trades=[]; position=None; account=START_CAPITAL; equity=[START_CAPITAL]
    atr=compute_atr(df['high'],df['low'],df['close'],14)
    min_lot=MIN_LOTS.get(instrument,1000); spc=SPREAD.get(instrument,0.001)
    op,hi,lo,cl=df['open'].values,df['high'].values,df['low'].values,df['close'].values
    sv=signals.values if hasattr(signals,'values') else signals
    av=atr.values if hasattr(atr,'values') else atr; nb=len(df)
    for i in range(1,nb):
        co,ch,cl_=op[i],hi[i],lo[i]; cs=sv[i] if i<len(sv) else 0
        ps_=sv[i-1] if (i-1)<len(sv) else 0; ca_=av[i] if i<len(av) else np.nan
        if position:
            d=position['direction']; sp=position['stop_price']; hit=False; xp=None
            if d==1 and cl_<=sp: hit=True; xp=sp
            elif d==-1 and ch>=sp: hit=True; xp=sp
            if not hit:
                if cs==0: xp=cl_
                elif (d==1 and cs<0) or (d==-1 and cs>0): xp=cl_
                else:
                    if d==1:
                        position['peak']=max(position['peak'],ch)
                        if not np.isnan(ca_): position['stop_price']=position['peak']-atr_mult*ca_
                    else:
                        position['trough']=min(position['trough'],cl_)
                        if not np.isnan(ca_): position['stop_price']=position['trough']+atr_mult*ca_
                    equity.append(account); continue
            if xp is not None:
                u=position['units']; ep=position['entry_price']; pnl=u*(xp-ep)*d
                cost=u*ep*spc+u*xp*spc; account+=pnl-cost
                trades.append({'pnl':pnl-cost,'gross_pnl':pnl,'direction':d,'hit_stop':hit}); position=None
        if not position and ps_==0 and cs!=0:
            if not np.isnan(ca_) and ca_>0:
                sd=ca_*atr_mult
                if sd>0:
                    ru=round_units(account*BASE_RISK/(sd*co),min_lot)
                    if ru>=min_lot:
                        direction=1 if cs>0 else -1
                        position={'direction':direction,'units':ru,'entry_price':co,
                                  'stop_price':co-direction*sd,'peak':ch if direction==1 else co,
                                  'trough':cl_ if direction==-1 else co}
        equity.append(account)
    if position:
        xp=cl[-1]; u=position['units']; ep=position['entry_price']
        pnl=u*(xp-ep)*position['direction']; cost=u*ep*spc+u*xp*spc; account+=pnl-cost
        trades.append({'pnl':pnl-cost,'gross_pnl':pnl,'direction':position['direction'],'hit_stop':False})
    equity.append(account)
    eq=np.array(equity); cum=eq/START_CAPITAL; rm=np.maximum.accumulate(cum); dd=(cum-rm)/rm*100
    wins=[t['pnl'] for t in trades if t['pnl']>0]; losses=[t['pnl'] for t in trades if t['pnl']<0]
    pf=sum(wins)/abs(sum(losses)) if losses else 99
    rets=np.diff(eq)/eq[:-1]; sh=np.sqrt(252*6)*np.mean(rets)/(np.std(rets)+1e-10) if len(rets)>1 else 0
    return {'trades':trades,'equity':equity,'final_capital':round(account,2),
            'total_return_pct':round((account/START_CAPITAL-1)*100,2),
            'max_drawdown_pct':round(dd.min(),2),'profit_factor':round(pf,3),
            'win_rate_pct':round(len(wins)/len(trades)*100,1) if trades else 0,
            'sharpe_ratio':round(sh,3),'num_trades':len(trades)}

def compute_kelly(trades):
    if not trades: return KELLY_MAX
    gross=np.array([t['gross_pnl'] for t in trades]); wins=gross[gross>0]; losses=gross[gross<0]
    if len(wins)==0 or len(losses)==0: return KELLY_MAX
    p=len(wins)/len(gross); avg_win=np.mean(wins); avg_loss=abs(np.mean(losses))
    if avg_loss==0: return KELLY_MAX
    wl_ratio=avg_win/avg_loss; kelly=(p*wl_ratio-(1-p))/wl_ratio
    return max(KELLY_MIN, min(KELLY_MAX, kelly))

def status_for(oos, kelly_pct):
    ret=oos['total_return_pct']; dd=oos['max_drawdown_pct']; sh=oos.get('sharpe_ratio',0)
    trades=oos.get('num_trades',0)
    if trades < 20: return '⚠️ LOW_TRADES'
    if sh > 0.3 and dd > -25: return '✅ PASS'
    elif sh > 0.15 or ret > 0: return '⚠️ MARGINAL'
    else: return '❌ FAIL'

# ─── MAIN ───
timeframes = ['H4', 'D']
all_results = {}

for tf in timeframes:
    print(f"\n{'#'*80}")
    print(f"# TIMEFRAME: {tf}")
    print(f"{'#'*80}")
    all_results[tf] = {}

    for stk, cfg in STRATEGIES.items():
        print(f"\n{'='*60}")
        print(f"  Strategy: {stk} ({tf})")
        print(f"{'='*60}")
        st_fn = cfg['fn']; strat_keys = cfg['strat_keys']; atr_key = cfg['atr_key']
        param_keys = strat_keys + [atr_key]
        combos = list(product(*[cfg['params'][k] for k in param_keys]))

        st_results = {}
        for sym in INSTRUMENTS:
            full = load_data(sym, tf)
            if full.empty:
                print(f"  {sym}: NO DATA"); continue

            is_mask = (full.index <= IS_END) & (full.index >= IS_START)
            oos_mask = full.index >= OOS_START
            is_df = full[is_mask]; oos_df = full[oos_mask]
            bars = len(oos_df)

            if len(is_df) < 200 or len(oos_df) < 200:
                print(f"  {sym}: INSUFFICIENT DATA (IS={len(is_df)}, OOS={len(oos_df)})")
                continue

            best = None; best_cap = -999
            for combo in combos:
                kw = dict(zip(param_keys, combo))
                strat_kw = {k: v for k, v in kw.items() if k != atr_key}
                atr_mult = kw[atr_key]
                try:
                    sigs = st_fn(is_df['close'], is_df['high'], is_df['low'], is_df['volume'], **strat_kw)
                    res = run_bt(is_df, sigs, sym, atr_mult=atr_mult)
                    if res['final_capital'] > best_cap:
                        best_cap = res['final_capital']
                        best = {'params': kw, 'res': res}
                except Exception as e:
                    pass

            if not best:
                print(f"  {sym}: NO VALID COMBOS"); continue

            bw = best['params']
            strat_kw = {k: v for k, v in bw.items() if k != atr_key}
            atr_mult = bw[atr_key]
            try:
                oos_sigs = st_fn(oos_df['close'], oos_df['high'], oos_df['low'], oos_df['volume'], **strat_kw)
                oos_raw = run_bt(oos_df, oos_sigs, sym, atr_mult=atr_mult)
            except:
                print(f"  {sym}: OOS FAILED"); continue

            oos_kelly = compute_kelly(oos_raw['trades'])
            wins_g = [t['gross_pnl'] for t in oos_raw['trades'] if t['gross_pnl']>0]
            losses_g = [t['gross_pnl'] for t in oos_raw['trades'] if t['gross_pnl']<0]
            oos_pf = sum(wins_g)/abs(sum(losses_g)) if losses_g else 99
            st = status_for(oos_raw, oos_kelly)

            print(f"  {sym:12s} {st} | IS=${best_cap:,.0f} | OOS=${oos_raw['final_capital']:,.0f} "
                  f"({oos_raw['total_return_pct']:+.1f}%) | DD={oos_raw['max_drawdown_pct']:+.1f}% | "
                  f"PF={oos_pf:.2f} | WR={oos_raw['win_rate_pct']:.0f}% | Tr={oos_raw['num_trades']} | "
                  f"Kelly={oos_kelly*100:.2f}% | {bw}")

            st_results[sym] = {
                'strategy': stk,
                'params': bw,
                'is': {'final_capital': best_cap, 'num_trades': best['res']['num_trades']},
                'oos': {**oos_raw, 'kelly_pct': round(oos_kelly*100, 3), 'profit_factor': round(oos_pf, 3)},
                'status': st,
            }

        all_results[tf][stk] = st_results
        pass_ct = sum(1 for v in st_results.values() if v['status']=='✅')
        marg_ct = sum(1 for v in st_results.values() if v['status']=='⚠️')
        fail_ct = sum(1 for v in st_results.values() if v['status']=='❌')
        print(f"\n  >> {stk} ({tf}): {pass_ct} pass / {marg_ct} marginal / {fail_ct} fail")

# Save
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
out = os.path.join(OUTPUT, f'full_optimize_{ts}.json')
with open(out, 'w') as f:
    json.dump(all_results, f, indent=2, default=str)

# Print summary
print(f"\n{'='*100}")
print("FINAL SUMMARY")
print(f"{'='*100}")
hdr = f"{'Strategy':<22} | {'TF':>3} | {'Pass':>4} {'Marg':>5} {'Fail':>5} | Best OOS Ret | Best OOS PF"
print(hdr)
print('-'*len(hdr))
for tf in timeframes:
    for stk in STRATEGIES.keys():
        if stk in all_results.get(tf, {}):
            res = all_results[tf][stk]
            pass_ct = sum(1 for v in res.values() if v['status']=='✅')
            marg_ct = sum(1 for v in res.values() if v['status']=='⚠️')
            fail_ct = sum(1 for v in res.values() if v['status']=='❌')
            # Best OOS
            items = [(k,v) for k,v in res.items() if 'oos' in v]
            if items:
                best = max(items, key=lambda x: x[1]['oos'].get('total_return_pct',0))
                boos = best[1]['oos']
                print(f"{stk:<22} | {tf:>3} | {pass_ct:>4} {marg_ct:>5} {fail_ct:>5} | {boos.get('total_return_pct',0):>+10.1f}% | {boos.get('profit_factor',0):>9.2f}")

print(f"\nSaved: {out}")
