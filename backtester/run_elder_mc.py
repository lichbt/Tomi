#!/usr/bin/env python3
"""Monte Carlo for Elder's Impulse — 10K sims | 5yr horizon | OOS 2020-2025"""
import sys, json, os, glob
from datetime import datetime
import numpy as np
import pandas as pd
import warnings, importlib.util
warnings.filterwarnings('ignore')

spec = importlib.util.spec_from_file_location("elder", "/Users/lich/.openclaw/workspace/strategies/strategy_elders_impulse.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
strategy_elders_impulse = mod.strategy_elders_impulse

CODER_CACHE = '/Users/lich/.openclaw/workspace-coder/data/cache'
OUTPUT = '/Users/lich/.openclaw/workspace/backtester'
SPREAD = {'BTC_USD':0.0010,'XAU_USD':0.0005,'BCO_USD':0.0012,'USD_TRY':0.0008,'NAS100_USD':0.0004,'XAG_USD':0.0008}
MIN_LOTS = {'BTC_USD':0.001,'XAU_USD':0.1,'BCO_USD':1,'USD_TRY':1,'NAS100_USD':0.01,'XAG_USD':1}
BASE_RISK = 0.01; START_CAPITAL = 10000.0; OOS_START = '2020-01-01'
N_SIMS = 10000

# Best params from corrected backtest
BEST_PARAMS = {
    'BTC_USD':    {'ema_period':7,'macd_fast':8,'macd_slow':21,'macd_signal':7,'atr_mult':3.0},
    'XAU_USD':    {'ema_period':7,'macd_fast':8,'macd_slow':26,'macd_signal':7,'atr_mult':2.5},
    'XAG_USD':    {'ema_period':7,'macd_fast':8,'macd_slow':26,'macd_signal':7,'atr_mult':1.5},
    'BCO_USD':    {'ema_period':7,'macd_fast':8,'macd_slow':26,'macd_signal':7,'atr_mult':3.0},
    'USD_TRY':    {'ema_period':7,'macd_fast':8,'macd_slow':21,'macd_signal':7,'atr_mult':1.5},
    'NAS100_USD': {'ema_period':7,'macd_fast':8,'macd_slow':21,'macd_signal':7,'atr_mult':3.0},
}
INSTRUMENTS = list(BEST_PARAMS.keys())

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
                trades.append({'pnl':pnl-cost,'gross_pnl':pnl,'direction':d,'hit_stop':hit,'ep':ep,'xp':xp,'units':u}); position=None
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
        xp=cl[-1]; u=position['units']; ep=position['entry_price']; pnl=u*(xp-ep)*position['direction']
        cost=u*ep*spc+u*xp*spc; account+=pnl-cost
        trades.append({'pnl':pnl-cost,'gross_pnl':pnl,'direction':position['direction'],'hit_stop':False,'ep':ep,'xp':xp,'units':u})
    equity.append(account)
    eq=np.array(equity); cum=eq/START_CAPITAL; rm=np.maximum.accumulate(cum); dd=(cum-rm)/rm*100
    wins=[t['pnl'] for t in trades if t['pnl']>0]; losses=[t['pnl'] for t in trades if t['pnl']<0]
    pf=sum(wins)/abs(sum(losses)) if losses else 99
    n=len(equity); rets=np.diff(eq)/eq[:-1]; sh=np.sqrt(252*6)*np.mean(rets)/(np.std(rets)+1e-10) if len(rets)>1 else 0
    return {'trades':trades,'equity':equity,'final_capital':round(account,2),
            'total_return_pct':round((account/START_CAPITAL-1)*100,2),
            'max_drawdown_pct':round(dd.min(),2),'profit_factor':round(pf,3),
            'win_rate_pct':round(len(wins)/len(trades)*100,1) if trades else 0,
            'sharpe_ratio':round(sh,3),'num_trades':len(trades)}

def compute_kelly(trades):
    if not trades: return 0.01
    gross=np.array([t['gross_pnl'] for t in trades]); wins=gross[gross>0]; losses=gross[gross<0]
    if len(wins)==0 or len(losses)==0: return 0.01
    p=len(wins)/len(gross); avg_win=np.mean(wins); avg_loss=abs(np.mean(losses))
    if avg_loss==0: return 0.01
    wl_ratio=avg_win/avg_loss; kelly=(p*wl_ratio-(1-p))/wl_ratio
    kelly=max(0.0008, min(0.01, kelly)); return kelly

def monte_carlo(trades, n_sims=N_SIMS, years=5, bpy=252*6):
    pnls=np.array([t['pnl'] for t in trades]); n=len(trades); n_bars=int(years*bpy)
    np.random.seed(42); caps,dd_list,returns_list,ruin=[],[],[],0
    for _ in range(n_sims):
        idx=np.random.randint(0,n,size=n_bars); seq=pnls[idx]; capital=START_CAPITAL; peak=START_CAPITAL; mx_dd=0.0
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
        'ruin_prob_pct':round(ruin/n_sims*100,2),
        'cap_pct':{p:round(np.percentile(caps,p),1) for p in pcts},
        'ret_pct':{p:round(np.percentile(rets,p),2) for p in pcts},
        'dd_pct':{p:round(np.percentile(dds,p),2) for p in pcts},
        'mean_cap':round(np.mean(caps),2),
    }

if __name__=='__main__':
    print("="*80)
    print("ELDER'S IMPULSE — Monte Carlo | {} sims | 5yr OOS | {}".format(N_SIMS, ', '.join(INSTRUMENTS)))
    print("="*80)
    all_results={}

    for sym in INSTRUMENTS:
        print(f"\n{'='*60}\n{sym}\n{'='*60}")
        full=load_h4(sym)
        if full.empty: continue
        oos_start_ts=pd.Timestamp(OOS_START, tz='UTC')
        oos_mask=full.index>=oos_start_ts; oos_df=full[oos_mask]
        print(f"  OOS bars: {oos_df.shape[0]}")

        bw=BEST_PARAMS[sym]; strat_kw={k:v for k,v in bw.items() if k!='atr_mult'}
        sigs=strategy_elders_impulse(oos_df['close'],oos_df['high'],oos_df['low'],oos_df['volume'],**strat_kw)
        res=run_bt(oos_df,sigs,sym,atr_mult=bw['atr_mult'])

        kelly=compute_kelly(res['trades']); scale=kelly/BASE_RISK
        scaled_trades=[]
        for t in res['trades']:
            scaled_trades.append({'pnl':t['pnl']*scale,'gross_pnl':t['gross_pnl']})
        mc=monte_carlo(scaled_trades)

        print(f"  Params: {bw}")
        print(f"  Kelly: {kelly*100:.2f}% | Scale: {scale:.2f}x")
        print(f"  OOS: ${res['final_capital']:,.0f} ({res['total_return_pct']:+.1f}%) | "
              f"DD={res['max_drawdown_pct']:+.1f}% | PF={res['profit_factor']:.2f} | "
              f"WR={res['win_rate_pct']:.0f}% | Tr={res['num_trades']}")
        print(f"\n  Monte Carlo ({N_SIMS:,} sims, 5yr horizon):")
        print(f"  {'Pct':>6} | {'Cap$':>10} | {'Return%':>10} | {'MaxDD%':>8}")
        print(f"  {'-'*6}-+-{'-'*10}-+-{'-'*10}-+-{'-'*8}")
        for p in [5,10,25,50,75,90,95]:
            print(f"  P{p:>4}% | ${mc['cap_pct'][p]:>9,.0f} | {mc['ret_pct'][p]:>+9.1f}% | {mc['dd_pct'][p]:>+7.1f}%")
        print(f"  {'Ruin':>6}: {mc['ruin_prob_pct']:.2f}%")
        print(f"  {'Mean':>6}: ${mc['mean_cap']:>9,.0f}")

        all_results[sym]={
            'params':bw,'kelly_pct':kelly*100,'scale':scale,
            'backtest':res,'monte_carlo':mc,
        }

    # Summary table
    print(f"\n{'='*90}")
    print("SUMMARY — Elder's Impulse Monte Carlo")
    print(f"{'='*90}")
    hdr=f"{'Sym':>12} | {'OOS$':>8} {'OOS%':>6} {'DD%':>5} {'PF':>5} | {'P5 Cap$':>9} {'P50 Cap$':>9} {'P95 Cap$':>9} | {'Ruin%':>6} | {'P5 DD%':>6} {'P50 DD%':>7} {'P95 DD%':>6}"
    print(hdr)
    print('-'*len(hdr))
    for sym,v in sorted(all_results.items(), key=lambda x: x[1]['monte_carlo']['ret_pct'][50], reverse=True):
        bt=v['backtest']; mc=v['monte_carlo']
        print(f"{sym:>12} | ${bt['final_capital']:>7,.0f} {bt['total_return_pct']:>+5.1f}% {abs(bt['max_drawdown_pct']):>4.0f}% {bt['profit_factor']:>5.2f} | "
              f"${mc['cap_pct'][5]:>8,.0f} ${mc['cap_pct'][50]:>8,.0f} ${mc['cap_pct'][95]:>8,.0f} | {mc['ruin_prob_pct']:>5.1f}% | "
              f"{mc['dd_pct'][5]:>5.1f}% {mc['dd_pct'][50]:>6.1f}% {mc['dd_pct'][95]:>5.1f}%")

    ts=datetime.now().strftime('%Y%m%d_%H%M%S')
    out=os.path.join(OUTPUT,f'elder_mc_{ts}.json')
    with open(out,'w') as f: json.dump(all_results,f,indent=2,default=str)
    print(f"\nSaved: {out}")
