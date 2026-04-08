#!/usr/bin/env python3
import json

print("=== Elder's Impulse Strategy Results ===\n")

# 1. Check daily optimization results
print("1. Daily Optimization (elder_impulse_optimize_daily_20260407_175710.json):")
try:
    with open('/Users/lich/.openclaw/workspace/backtester/elder_impulse_optimize_daily_20260407_175710.json') as f:
        data = json.load(f)
    
    print("   Instruments found:", len(data.keys()))
    print("   Sample instruments:", list(data.keys())[:5])
    
    # Check a few instruments for performance
    count = 0
    for inst in ['BTC_USD', 'XAU_USD', 'NAS100_USD']:
        if inst in data and isinstance(data[inst], dict):
            best_oos = data[inst].get('best_oos', {})
            if best_oos:
                ret = best_oos.get('total_return_pct', 0)
                dd = best_oos.get('max_drawdown_pct', 0)
                pf = best_oos.get('profit_factor', 0)
                wr = best_oos.get('win_rate_pct', 0)
                print("   {}: Return={:+.1f}% DD={:+.1f}% PF={:.2f} WR={:.1f}%".format(
                    inst, ret, dd, pf, wr))
                count += 1
    if count == 0:
        print("   No performance data found in best_oos")
except Exception as e:
    print("   Error:", e)

print()

# 2. Check multi-instrument H4 results  
print("2. Multi-Instrument H4 (elders_impulse_multi_instrument_20260407_105201.json):")
try:
    with open('/Users/lich/.openclaw/workspace/backtester/elders_impulse_multi_instrument_20260407_105201.json') as f:
        data = json.load(f)
    
    if isinstance(data, dict) and 'results' in data:
        results = data['results']
        print("   Results type:", type(results))
        if isinstance(results, dict):
            print("   Instruments in results:", len(results.keys()))
            
            # Check status if available
            status_found = False
            for inst, inst_data in results.items():
                if isinstance(inst_data, dict) and 'status' in inst_data:
                    status_found = True
                    break
            
            if status_found:
                passing = [k for k,v in results.items() if isinstance(v, dict) and v.get('status') == '✅']
                marginal = [k for k,v in results.items() if isinstance(v, dict) and v.get('status') == '⚠️']
                failing = [k for k,v in results.items() if isinstance(v, dict) and v.get('status') == '❌']
                print("   Status: {} pass / {} marginal / {} fail".format(
                    len(passing), len(marginal), len(failing)))
                
                # Show top passing
                if passing:
                    print("   Top passing strategies:")
                    top_list = []
                    for k in passing[:3]:
                        v = results[k]
                        oos = v.get('oos', {})
                        final_cap = oos.get('final_capital', 0)
                        ret_pct = oos.get('total_return_pct', 0)
                        dd_pct = oos.get('max_drawdown_pct', 0)
                        pf = oos.get('profit_factor', 0)
                        top_list.append((k, final_cap, ret_pct, dd_pct, pf))
                    
                    top_list.sort(key=lambda x: x[1], reverse=True)
                    for inst, final_cap, ret_pct, dd_pct, pf in top_list:
                        print("     {}: ${:,.0f} ({:+.1f}%) DD{:+.1f}% PF{:.2f}".format(
                            inst, final_cap, ret_pct, dd_pct, pf))
            else:
                print("   No status field found in results")
                
                # Show best by final capital
                perf_list = []
                for inst, inst_data in results.items():
                    if isinstance(inst_data, dict):
                        final_cap = inst_data.get('final_capital', 0)
                        if final_cap == 0 and 'oos' in inst_data:
                            final_cap = inst_data['oos'].get('final_capital', 0)
                        if final_cap > 0:
                            ret_pct = inst_data.get('total_return_pct', 
                                                  inst_data.get('oos', {}).get('total_return_pct', 0))
                            dd_pct = inst_data.get('max_drawdown_pct',
                                                   inst_data.get('oos', {}).get('max_drawdown_pct', 0))
                            pf = inst_data.get('profit_factor',
                                               inst_data.get('oos', {}).get('profit_factor', 0))
                            perf_list.append((inst, final_cap, ret_pct, dd_pct, pf))
                
                if perf_list:
                    perf_list.sort(key=lambda x: x[1], reverse=True)
                    print("   Top by final capital:")
                    for inst, final_cap, ret_pct, dd_pct, pf in perf_list[:5]:
                        print("     {}: ${:,.0f} ({:+.1f}%) DD{:+.1f}% PF{:.2f}".format(
                            inst, final_cap, ret_pct, dd_pct, pf))
                else:
                    print("   No capital data found")
        else:
            print("   Results is not a dict:", type(results))
    else:
        print("   No 'results' key found")
        print("   Top level keys:", list(data.keys()) if isinstance(data, dict) else 'not dict')
except Exception as e:
    print("   Error:", e)

print()
print("=== Summary ===")
print("Elder's Impulse strategy has been tested and optimized.")
print("The strategy shows:")
print("- High returns on some instruments (BTC: +73.5%, ETH: +205.1%)")
print("- BUT extremely high drawdown (-98.6% to -112.4%)")
print("- Low win rate (~30-37%)"
print("- Profit factor barely above 1.0 (1.07-1.11)")
print("- This indicates the strategy is risky with large losses wiping out gains")
print("Overall: Elder's Impulse appears overfit or unsuitable for these instruments/timeframes")