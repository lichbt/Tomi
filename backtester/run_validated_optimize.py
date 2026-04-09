#!/usr/bin/env python3
"""Optimize 4 validated strategies: RSI2 Connors, Kalman MR, Cointegration MR, ATR-Scaled Triple EMA."""
import sys, json, os, glob
from datetime import datetime
from itertools import product
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, '/Users/lich/.openclaw/workspace/shared/strategies')

from strategy_rsi2_connors import strategy_rsi2_connors
from strategy_kalman_mean_reversion import strategy_kalman_mean_reversion
from strategy_cointegration_pairs import strategy_cointegration_pairs
from strategy_atr_scaled_mean_reversion import strategy_atr_scaled_mean_reversion

CODER_CACHE = '/Users/lich/.openclaw/workspace-coder/data/cache'
OUTPUT = '/Users/lich/.openclaw/workspace/backtester'
os.makedirs(OUTPUT, exist_ok=True)

# All instruments with H4 and/or Daily data
ALL_INSTRUMENTS = [
    'BTC_USD','ETH_USD','XAU_USD','XAG_USD','BCO_USD','NAS100_USD','USD_TRY',
    'CORN_USD','NATGAS_USD','EUR_USD','GBP_USD','AUD_USD','NZD_USD','USD_CAD',
    'USD_CHF','EUR_GBP','EUR_JPY','GBP_JPY','EUR_AUD','EUR_CHF','EUR_CAD',
    'AUD_USD','AUD_JPY','AUD_NZD','AUD_CHF','GBP_CHF','GBP_AUD','GBP_CAD',
    'GBP_SGD','EUR_NOK','EUR_SEK','EUR_PLN','EUR_TRY','EUR_ZAR','GBP_ZAR',
    'CHF_JPY','CHF_HKD','HKD_JPY','CAD_CHF','CAD_JPY','CAD_HKD','CAD_SGD',
    'AUD_HKD','AUD_SGD','SGD_JPY','NZD_CAD','NZD_CHF','NZD_JPY','SGD_HKD',
    'EUR_HKD','EUR_SGD','GBP_HKD','GBP_NZD','GBP_PLN','EUR_DKK','EUR_CZK',
    'EUR_HUF','CHF_ZAR','HKD_SGD',
]
# Majors subset
MAJORS = ['BTC_USD','ETH_USD','XAU_USD','XAG_USD','BCO_USD','NAS100_USD','USD_TRY','CORN_USD','NATGAS_USD']
FOREX_MAJORS = ['EUR_USD','GBP_USD','AUD_USD','NZD_USD','USD_CAD','USD_CHF','EUR_GBP','EUR_JPY','GBP_JPY']

SPREADS = {
    'BTC_USD':0.0010,'ETH_USD':0.0010,'XAU_USD':0.0005,'XAG_USD':0.0008,'BCO_USD':0.0012,
    'NAS100_USD':0.0004,'USD_TRY':0.0008,'CORN_USD':0.001,'NATGAS_USD':0.001,
    'EUR_USD':0.0002,'GBP_USD':0.0003,'AUD_USD':0.0003,'NZD_USD':0.0003,
    'USD_CAD':0.0003,'USD_CHF':0.0003,'EUR_GBP':0.0003,'EUR_JPY':0.0004,
    'GBP_JPY':0.0005,'EUR_AUD':0.0004,'EUR_CHF':0.0004,'EUR_CAD':0.0004,
    'AUD_JPY':0.0004,'AUD_NZD':0.0004,'GBP_CHF':0.0004,'GBP_AUD':0.0004,
    'GBP_CAD':0.0004,'EUR_NOK':0.0004,'EUR_SEK':0.0004,'EUR_PLN':0.0004,
    'CHF_JPY':0.0005,'CAD_JPY':0.0005,'AUD_HKD':0.0004,'NZD_CAD':0.0003,
    'NZD_CHF':0.0003,'NZD_JPY':0.0004,'GBP_SGD':0.0005,'EUR_SGD':0.0005,
    'GBP_HKD':0.0004,'EUR_HKD':0.0004,'GBP_NZD':0.0004,'GBP_PLN':0.0004,
    'EUR_TRY':0.0008,'EUR_ZAR':0.0006,'GBP_ZAR':0.0006,'CHF_ZAR':0.0006,
    'CHF_HKD':0.0004,'CAD_CHF':0.0003,'CAD_HKD':0.0004,'CAD_SGD':0.0004,
    'AUD_CHF':0.0004,'AUD_SGD':0.0005,'SGD_JPY':0.0005,'HKD_JPY':0.0005,
    'EUR_DKK':0.0003,'EUR_CZK':0.0004,'EUR_HUF':0.0004,'HKD_SGD':0.0004,
}
MIN_LOTS = {
    'BTC_USD':0.001,'ETH_USD':0.01,'XAU_USD':0.1,'XAG_USD':1,'BCO_USD':1,
    'NAS100_USD':0.01,'USD_TRY':1,'CORN_USD':1,'NATGAS_USD':1,
    'EUR_USD':1000,'GBP_USD':1000,'AUD_USD':1000,'NZD_USD':1000,'USD_CAD':1000,
    'USD_CHF':1000,'EUR_GBP':1000,'EUR_JPY':1000,'GBP_JPY':1000,'EUR_AUD':1000,
    'EUR_CHF':1000,'EUR_CAD':1000,'AUD_JPY':1000,'AUD_NZD':1000,'GBP_CHF':1000,
    'GBP_AUD':1000,'GBP_CAD':1000,'EUR_NOK':1000,'EUR_SEK':1000,'EUR_PLN':1000,
    'CHF_JPY':1000,'CAD_JPY':1000,'AUD_HKD':1000,'NZD_CAD':1000,
    'NZD_CHF':1000,'NZD_JPY':1000,'GBP_SGD':1000,'EUR_SGD':1000,
    'GBP_HKD':1000,'EUR_HKD':1000,'GBP_NZD':1000,'GBP_PLN':1000,
    'EUR_TRY':1000,'EUR_ZAR':1000,'GBP_ZAR':1000,'CHF_ZAR':1000,
    'CHF_HKD':1000,'CAD_CHF':1000,'CAD_HKD':1000,'CAD_SGD':1000,
    'AUD_CHF':1000,'AUD_SGD':1000,'SGD_JPY':1000,'HKD_JPY':1000,
    'EUR_DKK':1000,'EUR_CZK':1000,'EUR_HUF':1000,'HKD_SGD':1000,
}
BASE_RISK = 0.01; KELLY_MIN = 0.0008; KELLY_MAX = 0.0100; START_CAPITAL = 10000.0
IS_END = pd.Timestamp('2019-12-31', tz='UTC'); IS_START = pd.Timestamp('2015-01-01', tz='UTC')
OOS_START = pd.Timestamp('2020-01-01', tz='UTC')

def get_spread(sym):
    for k, v in SPREADS.items():
        if sym.startswith(k.rstrip('_')): return v
    return 0.001

def get_min_lot(sym):
    for k, v in MIN_LOTS.items():
        if sym.startswith(k.rstrip('_')): return v
    return 1.0

def load_data(sym, tf):
    suffix = tf
    path = os.path.join(CODER_CACHE, f'{sym}_{suffix}.parquet')
    if not os.path.exists(path):
        m = glob.glob(os.path.join(CODER_CACHE, f'{sym}_{suffix}*.parquet'))
        if m: path = m[0]
    if not os.path.exists(path): return pd.DataFrame()
    df = pd.read_parquet(path)
    if 'Open' in df.columns:
        df = df.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'})
        df.index.name = 'timestamp'
    cols = [c for c in ['open','high','low','close','volume'] if c in df.columns]
    return df[cols] if len(df)>100 else pd.DataFrame()

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
    min_lot=get_min_lot(instrument); spc=get_spread(instrument)
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
                trades.append({'pnl':pnl-cost,'gross_pnl':pnl}); position=None
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
        trades.append({'pnl':pnl-cost,'gross_pnl':pnl})
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

def status_for(oos):
    ret=oos['total_return_pct']; dd=oos['max_drawdown_pct']; sh=oos.get('sharpe_ratio',0); tr=oos.get('num_trades',0)
    if tr < 10: return 'LOW_TRADES'
    if sh > 0.3 and dd > -25: return 'PASS'
    elif sh > 0.15 or ret > 0: return 'MARGINAL'
    else: return 'FAIL'

# ─── Strategy configs ───
# RSI2 Connors: sma_long, rsi_period=2, rsi_entry_long, rsi_entry_short, rsi_exit_long, rsi_exit_short, sma_exit_period
RSI2_PARAMS = {
    'sma_long_period': [100, 200],
    'rsi_period': [2],
    'rsi_entry_long': [5, 10],
    'rsi_entry_short': [90, 95],
    'rsi_exit_long': [50, 65],
    'rsi_exit_short': [35, 50],
    'sma_exit_period': [5, 10],
    'atr_mult': [1.5, 2.0, 2.5, 3.0],
}
RSI2_STRAT_KEYS = ['sma_long_period','rsi_period','rsi_entry_long','rsi_entry_short','rsi_exit_long','rsi_exit_short','sma_exit_period']
RSI2_ATR_KEY = 'atr_mult'

# Kalman MR v3: lookback_short, transition_cov, obs_cov, adx_threshold (min/max_hold are backtest params)
KALMAN_PARAMS = {
    'lookback_short': [3, 5, 7],
    'transition_cov': [0.005, 0.01, 0.05],
    'obs_cov': [0.5, 1.0],
    'adx_threshold': [20.0, 25.0],
    'atr_mult': [1.5, 2.0, 2.5],
}
KALMAN_STRAT_KEYS = ['lookback_short','transition_cov','obs_cov','adx_threshold']
KALMAN_ATR_KEY = 'atr_mult'

# Cointegration MR: lookback, entry_threshold, exit_threshold, atr_mult
COINT_PARAMS = {
    'lookback': [10, 20, 30],
    'entry_threshold': [1.5, 2.0, 2.5],
    'exit_threshold': [0.0, 0.5],
    'atr_mult': [1.5, 2.0, 2.5],
}
COINT_STRAT_KEYS = ['lookback','entry_threshold','exit_threshold']
COINT_ATR_KEY = 'atr_mult'

# ATR-Scaled Triple EMA: ema_fast, ema_med, ema_long, atr_period, atr_multiplier, min_hold_bars
ATRS_PARAMS = {
    'ema_fast_period': [5, 10, 20],
    'ema_med_period': [20, 50],
    'ema_long_period': [50, 100],
    'atr_period': [14],
    'atr_multiplier': [1.0, 1.5, 2.0],
    'min_hold_bars': [1, 2, 4],
}
ATRS_STRAT_KEYS = ['ema_fast_period','ema_med_period','ema_long_period','atr_period','atr_multiplier','min_hold_bars']
ATRS_ATR_KEY = None  # uses atr_multiplier from params

STRAT_CONFIGS = {
    'rsi2_connors': {
        'fn': strategy_rsi2_connors,
        'params': RSI2_PARAMS,
        'strat_keys': RSI2_STRAT_KEYS,
        'atr_key': RSI2_ATR_KEY,
        'instruments': MAJORS + FOREX_MAJORS,
        'timeframes': ['H4', 'D'],
    },
    'kalman_mr': {
        'fn': strategy_kalman_mean_reversion,
        'params': KALMAN_PARAMS,
        'strat_keys': KALMAN_STRAT_KEYS,
        'atr_key': KALMAN_ATR_KEY,
        'instruments': MAJORS,
        'timeframes': ['H4', 'D'],
    },
    'atr_scaled': {
        'fn': strategy_atr_scaled_mean_reversion,
        'params': ATRS_PARAMS,
        'strat_keys': ATRS_STRAT_KEYS,
        'atr_key': ATRS_ATR_KEY,
        'instruments': MAJORS,
        'timeframes': ['H4', 'D'],
    },
}

all_results = {}

for stk, cfg in STRAT_CONFIGS.items():
    print(f"\n{'='*70}")
    print(f"  Strategy: {stk}")
    print(f"{'='*70}")
    st_fn = cfg['fn']; strat_keys = cfg['strat_keys']; atr_key = cfg['atr_key']
    param_keys = strat_keys + ([atr_key] if atr_key else [])
    combos = list(product(*[cfg['params'][k] for k in param_keys]))
    print(f"  Grid: {len(combos)} combos x {len(cfg['instruments'])} instruments x {len(cfg['timeframes'])} TFs")

    st_results = {}
    for tf in cfg['timeframes']:
        for sym in cfg['instruments']:
            full = load_data(sym, tf)
            if full.empty:
                continue

            is_mask = (full.index <= IS_END) & (full.index >= IS_START)
            oos_mask = full.index >= OOS_START
            is_df = full[is_mask]; oos_df = full[oos_mask]
            if len(is_df) < 200 or len(oos_df) < 100:
                continue

            best=None; best_cap=-999
            for combo in combos:
                kw=dict(zip(param_keys, combo))
                strat_kw={k:v for k,v in kw.items() if k!=atr_key}
                if atr_key:
                    atr_mult_use=kw.get(atr_key, 2.0)
                else:
                    atr_mult_use=kw.get('atr_multiplier', 2.0)
                try:
                    sigs=st_fn(is_df, **strat_kw)
                    if sigs is None or len(sigs)==0: continue
                    res=run_bt(is_df, sigs, sym, atr_mult=atr_mult_use)
                    if res['final_capital']>best_cap:
                        best_cap=res['final_capital']
                        best={'params':kw,'res':res}
                except:
                    pass

            if not best: continue

            bw=best['params']
            strat_kw={k:v for k,v in bw.items() if k!=atr_key}
            if atr_key:
                atr_mult_use=bw.get(atr_key, 2.0)
            else:
                atr_mult_use=bw.get('atr_multiplier', 2.0)
            try:
                oos_sigs=st_fn(oos_df, **strat_kw)
                if oos_sigs is None or len(oos_sigs)==0: continue
                oos_raw=run_bt(oos_df, oos_sigs, sym, atr_mult=atr_mult_use)
            except:
                continue

            kelly=compute_kelly(oos_raw['trades'])
            wins_g=[t['gross_pnl'] for t in oos_raw['trades'] if t['gross_pnl']>0]
            losses_g=[t['gross_pnl'] for t in oos_raw['trades'] if t['gross_pnl']<0]
            pf=sum(wins_g)/abs(sum(losses_g)) if losses_g else 99
            st=status_for(oos_raw)

            key=f"{sym}_{tf}"
            print(f"  {sym:12s} ({tf}) {st:10s} | IS=${best_cap:,.0f} | OOS=${oos_raw['final_capital']:,.0f} "
                  f"({oos_raw['total_return_pct']:+.1f}%) | DD={oos_raw['max_drawdown_pct']:+.1f}% | "
                  f"PF={pf:.2f} | WR={oos_raw['win_rate_pct']:.0f}% | Tr={oos_raw['num_trades']} | "
                  f"Kelly={kelly*100:.2f}%")

            st_results[key]={
                'strategy':stk,'sym':sym,'tf':tf,'params':bw,
                'is':{'final_capital':best_cap,'num_trades':best['res']['num_trades']},
                'oos':{**oos_raw,'kelly_pct':round(kelly*100,3),'profit_factor':round(pf,3)},
                'status':st,
            }

    all_results[stk]=st_results
    pass_ct=sum(1 for v in st_results.values() if 'PASS' in str(v.get('status','')))
    marg_ct=sum(1 for v in st_results.values() if 'MARGINAL' in str(v.get('status','')))
    fail_ct=sum(1 for v in st_results.values() if 'FAIL' in str(v.get('status','')))
    print(f"\n  >> {stk}: {pass_ct} pass / {marg_ct} marginal / {fail_ct} fail")

ts=datetime.now().strftime('%Y%m%d_%H%M%S')
out=os.path.join(OUTPUT,f'validated_optimize_{ts}.json')
with open(out,'w') as f: json.dump(all_results,f,indent=2,default=str)

# Summary
print(f"\n{'='*80}")
print("FINAL SUMMARY — 4 Validated Strategies")
print(f"{'='*80}")
for stk in STRAT_CONFIGS.keys():
    res=all_results.get(stk,{})
    if not res: continue
    items=[(k,v) for k,v in res.items() if 'oos' in v]
    if not items: continue
    best=max(items, key=lambda x: x[1]['oos'].get('total_return_pct',0))
    boos=best[1]['oos']
    pass_ct=sum(1 for v in res.values() if 'PASS' in str(v.get('status','')))
    marg_ct=sum(1 for v in res.values() if 'MARGINAL' in str(v.get('status','')))
    fail_ct=sum(1 for v in res.values() if 'FAIL' in str(v.get('status','')))
    print(f"  {stk:20s}: {pass_ct:3d}P / {marg_ct:3d}M / {fail_ct:3d}F | Best: {best[0]} {boos.get('total_return_pct',0):+.1f}% DD{boos.get('max_drawdown_pct',0):+.1f}% PF{boos.get('profit_factor',0):.2f} Sharpe{boos.get('sharpe_ratio',0):.2f}")

print(f"\nSaved: {out}")
