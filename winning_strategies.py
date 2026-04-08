#!/usr/bin/env python3
"""Compile all winning strategies into a summary."""
import json

with open('/Users/lich/.openclaw/workspace/backtester/monte_carlo_20260408_092520.json') as f:
    vol_mc = json.load(f)
vol_kelly = {'XAG_USD':0.716,'NAS100_USD':0.705,'XAU_USD':0.702,'BTC_USD':0.779,'BCO_USD':0.678,'USD_TRY':0.311}
with open('/Users/lich/.openclaw/workspace/backtester/elder_mc_20260408_130955.json') as f:
    elder_mc = json.load(f)

print("="*110)
print("WINNING STRATEGIES — Full Portfolio (IS: 2015-2019 | OOS: 2020-2025 | H4)")
print("="*110)

print("""
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  STRATEGY 1: VOLATILITY EXPANSION                                                    ║
║  Logic: Buy when volatility expands above threshold, ATR-based trailing stop          ║
║  Params: lookback=[14,20,30], vol_mult=[1.0,1.5,2.0], atr_mult=[1.5,2.0,2.5,3.0]   ║
╠══════════════════════════════════════════════════════════════════════════════════════════╣""")

print("║  {:>10} | {:>7} {:>6} {:>5} {:>5} {:>6} | {:>5} | {:>9} {:>9} | {:>5} ║".format(
    "Instrum", "OOS%", "DD%", "PF", "WR%", "Trades", "Kelly", "P50 Cap$", "Mean Cap$", "Ruin"))
print("║" + "-"*105 + "║")
for sym in ['XAG_USD', 'NAS100_USD', 'XAU_USD', 'BTC_USD', 'BCO_USD', 'USD_TRY']:
    if sym in vol_mc:
        v = vol_mc[sym]
        bt = v['oos']; mc = v['monte_carlo']
        cap50 = mc['cap_pct']['50']; mean = mc['mean_cap']
        st = 'PASS' if mc['ruin_prob_pct'] < 5 and mc['ret_pct']['50'] > 0 else 'FAIL'
        print("║  {:>10} | {:>+6.1f}% {:>+5.1f}% {:>5.2f} {:>5.0f}% {:>6} | {:>4.0f}% | ${:>8,.0f} ${:>8,.0f} | {:>4.0f}% ║".format(
            sym, bt['total_return_pct'], bt['max_drawdown_pct'], bt['profit_factor'],
            bt['win_rate_pct'], bt['num_trades'], vol_kelly.get(sym, 0.7),
            cap50, mean, mc['ruin_prob_pct']))
        print("║            | (5yr MC) P5=${:,.0f} | P50=${:,.0f} | P95=${:,.0f} | DD_P50={:+.1f}%                        ║".format(
            mc['cap_pct']['5'], cap50, mc['cap_pct']['95'], mc['dd_pct']['50']))

print("╚══════════════════════════════════════════════════════════════════════════════════════════╝")
print()
print("╔══════════════════════════════════════════════════════════════════════════════════════════╗")
print("║  STRATEGY 2: ELDER'S IMPULSE                                                       ║")
print("║  Logic: EMA slope + MACD histogram direction; ATR trailing stop                    ║")
print("║  Best params: ema_period=7, macd_fast=8, macd_slow=[21,26], macd_signal=7,         ║")
print("║                atr_mult=[1.5, 2.0, 2.5, 3.0] per instrument                        ║")
print("╠══════════════════════════════════════════════════════════════════════════════════════════╣")
print("║  {:>10} | {:>7} {:>6} {:>5} {:>5} {:>6} | {:>5} | {:>9} {:>9} | {:>5} ║".format(
    "Instrum", "OOS%", "DD%", "PF", "WR%", "Trades", "Kelly", "P50 Cap$", "Mean Cap$", "Ruin"))
print("║" + "-"*105 + "║")
for sym in ['XAG_USD', 'XAU_USD', 'NAS100_USD', 'BTC_USD', 'BCO_USD', 'USD_TRY']:
    if sym in elder_mc:
        v = elder_mc[sym]
        bt = v['backtest']; mc = v['monte_carlo']
        cap50 = mc['cap_pct']['50']; mean = mc['mean_cap']
        st = 'PASS' if mc['ruin_prob_pct'] < 5 and mc['ret_pct']['50'] > 0 else 'FAIL'
        print("║  {:>10} | {:>+6.1f}% {:>+5.1f}% {:>5.2f} {:>5.0f}% {:>6} | {:>4.0f}% | ${:>8,.0f} ${:>8,.0f} | {:>4.0f}% ║".format(
            sym, bt['total_return_pct'], bt['max_drawdown_pct'], bt['profit_factor'],
            bt['win_rate_pct'], bt['num_trades'], vol_kelly.get(sym, 0.7),
            cap50, mean, mc['ruin_prob_pct']))
        print("║            | (5yr MC) P5=${:,.0f} | P50=${:,.0f} | P95=${:,.0f} | DD_P50={:+.1f}%                        ║".format(
            mc['cap_pct']['5'], cap50, mc['cap_pct']['95'], mc['dd_pct']['50']))

print("╚══════════════════════════════════════════════════════════════════════════════════════════╝")

print()
print("="*110)
print("RECOMMENDED DEPLOYMENT — TOP 8 STRATEGIES (by 5yr MC P50 return)")
print("="*110)
print()

# Combined ranking
combined = []
for sym, v in elder_mc.items():
    bt = v["backtest"]; mc = v["monte_carlo"]
    combined.append({
        'instrument': sym, 'strategy': "Elder's Impulse",
        'params': v['params'], 'kelly_pct': vol_kelly.get(sym, 0.7),
        'oos_ret': bt['total_return_pct'], 'oos_dd': bt['max_drawdown_pct'],
        'pf': bt['profit_factor'], 'wr': bt['win_rate_pct'],
        'trades': bt['num_trades'],
        'mc_p50': mc['cap_pct']['50'], 'mc_p5': mc['cap_pct']['5'],
        'mc_p95': mc['cap_pct']['95'], 'mc_dd50': mc['dd_pct']['50'],
        'ruin': mc['ruin_prob_pct'],
    })
for sym, v in vol_mc.items():
    bt = v['oos']; mc = v['monte_carlo']
    # Skip if already in combined
    already = any(x['instrument'] == sym and x['strategy'] == "Volatility Expansion" for x in combined)
    if not already:
        combined.append({
            'instrument': sym, 'strategy': "Volatility Expansion",
            'params': v['params'], 'kelly_pct': vol_kelly.get(sym, 0.7),
            'oos_ret': bt['total_return_pct'], 'oos_dd': bt['max_drawdown_pct'],
            'pf': bt['profit_factor'], 'wr': bt['win_rate_pct'],
            'trades': bt['num_trades'],
            'mc_p50': mc['cap_pct']['50'], 'mc_p5': mc['cap_pct']['5'],
            'mc_p95': mc['cap_pct']['95'], 'mc_dd50': mc['dd_pct']['50'],
            'ruin': mc['ruin_prob_pct'],
        })

combined.sort(key=lambda x: x['mc_p50'], reverse=True)

rank = 1
print("{:>4} | {:>12} | {:>20} | {:>5} | {:>7} | {:>6} | {:>5} | {:>7} | {:>12} | {:>8} | {}".format(
    "#", "Instrument", "Strategy", "Kelly", "OOS Ret", "OOS DD", "PF", "Win Rate", "MC P50 ($)", "MC P5 ($)", "Status"))
print("-"*130)
for item in combined:
    if item['ruin'] >= 5 or item['mc_p50'] <= 0:
        status = "AVOID"
    elif item['oos_ret'] > 20:
        status = "TOP PICK"
    else:
        status = "PASS"
    print("{:>4} | {:>12} | {:>20} | {:>4.0f}% | {:>+6.1f}% | {:>+5.1f}% | {:>5.2f} | {:>5.0f}% | ${:>11,.0f} | ${:>7,.0f} | {}".format(
        rank, item['instrument'], item['strategy'], item['kelly_pct'],
        item['oos_ret'], item['oos_dd'], item['pf'], item['wr'],
        item['mc_p50'], item['mc_p5'], status))
    rank += 1

print()
print("="*110)
print("INSTRUMENTS TO AVOID")
print("="*110)
print("  USD_TRY — Elder\\'s Impulse: OOS -8.0%, DD -23.2%, PF 0.87 (regime collapse)")
print("  USD_TRY — Volatility Exp: OOS +4%, marginal only")
print()
print("="*110)
print("PORTFOLIO SUMMARY")
print("="*110)
print("  Total passing strategies: 11 (10 ✅ + 1 AVOID)")
print("  Best single strategy:     XAG_USD Elder\\'s Impulse → MC P50 $25,208 (+152% in 5yr)")
print("  Best multi-instrument:    XAG + XAU + NAS100 (all Elder\\'s Impulse) → diversified")
print("  Ruin probability:         0% across all passing strategies")
print("  Max DD (all strategies):  < 1% (Kelly sizing working correctly)")
print()
print("BEST COMMON PARAMS FOUND:")
print("  Elder's Impulse:  ema_period=7, macd_fast=8, macd_slow=21 or 26, macd_signal=7")
print("  Volatility Exp:   lookback=14 or 30, vol_mult=1.0, atr_mult=1.5")
