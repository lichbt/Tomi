#!/usr/bin/env python3
import json

with open('/Users/lich/.openclaw/workspace/backtester/portfolio_v13_h4_kelly_corrected_20260407_232857.json') as f:
    data = json.load(f)

passing = {k:v for k,v in data.items() if v['status']=='✅'}
marginal = {k:v for k,v in data.items() if v['status']=='⚠️'}
failing = {k:v for k,v in data.items() if v['status']=='❌'}

print("PORTFOLIO v13 CORRECTED BACKTEST RESULTS:")
print(f"  {len(passing)} pass / {len(marginal)} marginal / {len(failing)} fail")
print()

# Count by strategy
strat_count = {}
for k,v in data.items():
    st = v.get('strategy','Unknown')
    strat_count[st] = strat_count.get(st, {'pass':0,'marg':0,'fail':0})
    if v['status'] == '✅':
        strat_count[st]['pass'] += 1
    elif v['status'] == '⚠️':
        strat_count[st]['marg'] += 1
    else:
        strat_count[st]['fail'] += 1

print("BY STRATEGY:")
for st, counts in sorted(strat_count.items()):
    print(f"  {st:30s}: {counts['pass']:2d} pass / {counts['marg']:2d} marg / {counts['fail']:2d} fail")

print()
print("STRATEGIES NOT FULLY TESTED:")
for st, counts in strat_count.items():
    if counts['pass'] == 0:
        print(f"  {st}: 0 passing combos (need re-test)")

print()
print("Strategies tested:")
for k,v in data.items():
    o = v['oos']
    status = v['status']
    print(f"  {k:30s}: {v['strategy']:25s} {status} OOS=${o.get('final_capital',0):,.0f} ({o.get('total_return_pct',0):+.1f}%)")
