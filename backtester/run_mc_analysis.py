#!/usr/bin/env python3
"""
Monte Carlo for portfolio v13 — full trade-level P&L resampling
10,000 sims | 5-year horizon | OOS 2020-2025
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

CODER_CACHE = '/Users/lich/.openclaw/workspace-coder/data/cache'
OUTPUT = '/Users/lich/.openclaw/workspace/backtester'
SPREAD = {'BTC_USD':0.0010,'XAU_USD':0.0005,'BCO_USD':0.0012,'USD_TRY':0.0008,'NAS100_USD':0.0004,'XAG_USD':0.0008}
MIN_LOTS = {'BTC_USD':0.001,'XAU_USD':0.1,'BCO_USD':1,'USD_TRY':1,'NAS100_USD':0.01,'XAG_USD':1}
BASE_RISK = 0.01
START_CAPITAL = 10000.0
OOS_START = '2020-01-01'
N_SIMS = 10000
STRAT_FN = {
    'donchian': strategy_donchian_breakout,
    'macd': strategy_macd_momentum,
    'vol_exp': strategy_volatility_expansion,
    'adx': strategy_adx_trend,
    'ichimoku': strategy_ichimoku_cloud,
    'supertrend': strategy_supertrend_vol,
}
STRAT_KEYS = {
    'donchian': ['entry_period','atr_mult'],
    'macd': ['fast','slow','signal','atr_mult'],
    'vol_exp': ['lookback','vol_mult','atr_mult'],
    'adx': ['adx_period','adx_threshold','ema_period','atr_mult'],
    'ichimoku': ['t_period','k_period','s_period','atr_mult'],
    'supertrend': ['st_period','st_mult','atr_mult'],
}
STRATEGIES = [
    ('donchian',{'entry_period':[10,15,20,30,40],'atr_mult':[1.5,2.0,2.5,3.0]}),
    ('macd',{'fast':[8,12],'slow':[21,26,34],'signal':[7,9],'atr_mult':[1.5,2.0,2.5,3.0]}),
    ('vol_exp',{'lookback':[14,20,30],'vol_mult':[1.0,1.5,2.0],'atr_mult':[1.5,2.0,2.5,3.0]}),
    ('adx',{'adx_period':[7,14],'adx_threshold':[20,25,30],'ema_period':[20,50,100],'atr_mult':[1.5,2.0,2.5,3.0]}),
    ('ichimoku',{'t_period':[7,9],'k_period':[22,26],'s_period':[44,52],'atr_mult':[1.5,2.0,2.5,3.0]}),
    ('supertrend',{'st_period':[7,10,14],'st_mult':[2.0,3.0,4.0],'atr_mult':[1.5,2.0,2.5]}),
]
INSTRUMENTS = ['BTC_USD','XAU_USD','BCO_USD','USD_TRY','NAS100_USD','XAG_USD']

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

def run_backtest(df, signals, instrument, atr_mult=2.5):
    trades=[]; position=None; equity=[START_CAPITAL]; account=START_CAPITAL
    atr=compute_atr(df['high'],df['low'],df['close'],14)
    min_lot=MIN_LOTS.get(instrument,1000); spc=SPREAD.get(instrument,0.001)
    op,hi,lo,cl = df['open'].values,df['high'].values,df['low'].values,df['close'].values
    sv=signals.values if hasattr(signals,'values') else signals
    av=atr.values if hasattr(atr,'values') else atr; nb=len(df)
    for i in range(1,nb):
        co,ch,cl_ = op[i],hi[i],lo[i]
        cs=sv[i] if i<len(sv) else 0
        ps_=sv[i-1] if (i-1)<len(sv) else 0
        ca_=av[i] if i<len(av) else np.nan
        if position:
            d=position['direction']; sp=position['stop_price']
            hit=False; xp=None
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
                u=position['units']; ep=position['entry_price']
                pnl=u*(xp-ep)*d; cost=u*ep*spc+u*xp*spc
                account+=pnl-cost
                trades.append({'pnl':pnl-cost,'gross_pnl':pnl,'direction':d,'hit_stop':hit,'ep':ep,'xp':xp})
                position=None
        if not position and ps_==0 and cs!=0:
            if not np.isnan(ca_) and ca_>0:
                sd=ca_*atr_mult
                if sd>0:
                    ru=round_units(account*BASE_RISK/(sd*co),min_lot)
                    if ru>=min_lot:
                        direction=1 if cs>0 else -1
                        position={'direction':direction,'units':ru,'entry_price':co,'stop_price':co-direction*sd,'peak':ch if direction==1 else co,'trough':cl_ if direction==-1 else co}
        equity.append(account)
    if position:
        xp=cl[-1]; u=position['units']; ep=position['entry_price']
        pnl=u*(xp-ep)*position['direction']; cost=u*ep*spc+u*xp*spc
        account+=pnl-cost
        trades.append({'pnl':pnl-cost,'gross_pnl':pnl,'direction':position['direction'],'hit_stop':False,'ep':ep,'xp':xp})
    equity.append(account)
    eq=np.array(equity); cum=eq/START_CAPITAL; rm=np.maximum.accumulate(cum); dd=(cum-rm)/rm*100
    wins=[t['pnl'] for t in trades if t['pnl']>0]; losses=[t['pnl'] for t in trades if t['pnl']<0]
    pf=sum(wins)/abs(sum(losses)) if losses else 99
    n=len(equity)
    rets=np.diff(eq)/eq[:-1]; sh=np.sqrt(252*6)*np.mean(rets)/(np.std(rets)+1e-10) if len(rets)>1 else 0
    return {'trades':trades,'equity':equity,'final_capital':round(account,2),
            'total_return_pct':round((account/START_CAPITAL-1)*100,2),
            'max_drawdown_pct':round(dd.min(),2),'profit_factor':round(pf,3),
            'win_rate_pct':round(len(wins)/len(trades)*100,1) if trades else 0,
            'sharpe_ratio':round(sh,3),'num_trades':len(trades)}

def monte_carlo(trades, n_sims=N_SIMS, years=5, bpy=252*6):
    pnls=np.array([t['pnl'] for t in trades]); n=len(trades)
    n_bars=int(years*bpy); np.random.seed(42)
    caps,dd_list,returns_list,ruin=[],[],[],0
    for _ in range(n_sims):
        idx=np.random.randint(0,n,size=n_bars)
        seq=pnls[idx]; capital=START_CAPITAL; peak=START_CAPITAL; mx_dd=0.0
        for p in seq:
            capital+=p
            if capital>peak: peak=capital
            d=(peak-capital)/peak*100
            if d>mx_dd: mx_dd=d
            if capital<=0: ruin+=1; break
        caps.append(capital); dd_list.append(mx_dd)
        returns_list.append((capital/START_CAPITAL-1)*100)
    caps=np.array(caps); dds=np.array(dd_list); rets=np.array(returns_list)
    pcts=[5,10,25,50,75,90,95]
    return {
        'ruin_prob_pct': round(ruin/n_sims*100,2),
        'cap_pct': {p: round(np.percentile(caps,p),1) for p in pcts},
        'ret_pct': {p: round(np.percentile(rets,p),2) for p in pcts},
        'dd_pct': {p: round(np.percentile(dds,p),2) for p in pcts},
        'mean_cap': round(np.mean(caps),2),
    }

if __name__=='__main__':
    print("="*90)
    print(f"Monte Carlo — {N_SIMS:,} sims | 5yr OOS | Instruments: {', '.join(INSTRUMENTS)}")
    print("="*90)
    all_results={}

    for sym in INSTRUMENTS:
        print(f"\n{'='*60}\n{sym}\n{'='*60}")
        full=load_h4(sym)
        if full.empty: continue
        split=full.index.searchsorted(OOS_START,side='left')
        oos_d=full.iloc[split:]
        print(f"  OOS bars: {oos_d.shape[0]}")

        best=None; best_cap=-999
        for (stk,grid) in STRATEGIES:
            keys=STRAT_KEYS[stk]; combos=list(product(*[grid[k] for k in keys]))
            for combo in combos:
                kw=dict(zip(keys,combo))
                sigs=STRAT_FN[stk](oos_d['close'],oos_d['high'],oos_d['low'],oos_d['volume'],**kw)
                res=run_backtest(oos_d,sigs,sym)
                if res['num_trades']>=5 and res['final_capital']>best_cap:
                    best_cap=res['final_capital']
                    best={'strategy':stk,'params':kw,'res':res}

        if best:
            r=best['res']
            mc=monte_carlo(r['trades'])
            print(f"\n  [{best['strategy']}] Params: {best['params']}")
            print(f"  OOS: ${r['final_capital']:,.0f} | Ret={r['total_return_pct']:.1f}% | DD={r['max_drawdown_pct']:.1f}% | PF={r['profit_factor']:.2f} | WR={r['win_rate_pct']:.0f}% | Tr={r['num_trades']}")
            print(f"\n  Monte Carlo (P=cap$, R=return%, D=maxDD%):")
            print(f"  {'Pct':>6} | {'Cap$':>10} | {'Return%':>10} | {'MaxDD%':>8}")
            print(f"  {'-'*6}-+-{'-'*10}-+-{'-'*10}-+-{'-'*8}")
            for p in [5,10,25,50,75,90,95]:
                print(f"  P{p:>4}% | ${mc['cap_pct'][p]:>9,.0f} | {mc['ret_pct'][p]:>+9.1f}% | {mc['dd_pct'][p]:>+7.1f}%")
            print(f"  {'Ruin':>6}: {mc['ruin_prob_pct']:.2f}%")
            print(f"  {'Mean':>6}: ${mc['mean_cap']:>9,.0f}")
            all_results[sym]={'strategy':best['strategy'],'params':best['params'],
                             'oos':r,'monte_carlo':mc}

    # Summary
    print(f"\n{'='*90}")
    print("SUMMARY TABLE")
    print(f"{'='*90}")
    hdr=f"{'Sym':>12} | {'Strat':>10} | {'OOS$':>8} {'OOS%':>6} {'DD%':>5} {'PF':>5} | {'P5 Cap$':>9} {'P50 Cap$':>9} {'P95 Cap$':>9} | {'Ruin%':>6} | {'P5 DD%':>6} {'P50 DD%':>7} {'P95 DD%':>6}"
    print(hdr)
    print('-'*len(hdr))
    for sym, v in sorted(all_results.items(), key=lambda x: x[1]['monte_carlo']['ret_pct'][50], reverse=True):
        r=v['oos']; mc=v['monte_carlo']
        print(f"{sym:>12} | {v['strategy']:>10} | ${r['final_capital']:>7,.0f} {r['total_return_pct']:>+5.1f}% {abs(r['max_drawdown_pct']):>4.0f}% {r['profit_factor']:>5.2f} | ${mc['cap_pct'][5]:>8,.0f} ${mc['cap_pct'][50]:>8,.0f} ${mc['cap_pct'][95]:>8,.0f} | {mc['ruin_prob_pct']:>5.1f}% | {mc['dd_pct'][5]:>5.1f}% {mc['dd_pct'][50]:>6.1f}% {mc['dd_pct'][95]:>5.1f}%")

    ts=datetime.now().strftime('%Y%m%d_%H%M%S')
    out=os.path.join(OUTPUT,f'monte_carlo_{ts}.json')
    with open(out,'w') as f: json.dump(all_results,f,indent=2,default=str)
    print(f"\nSaved: {out}")
