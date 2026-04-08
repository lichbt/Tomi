#!/usr/bin/env python3
import json
import sys

def check_file(path):
    print(f"\n=== {path} ===")
    try:
        with open(path) as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            # Check if it's the optimization format with status
            if any('status' in str(v) for v in data.values() if isinstance(v, dict)):
                passing = [k for k,v in data.items() if isinstance(v, dict) and v.get('status') == '✅']
                marginal = [k for k,v in data.items() if isinstance(v, dict) and v.get('status') == '⚠️']
                failing = [k for k,v in data.items() if isinstance(v, dict) and v.get('status') == '❌']
                print(f"Results: {len(passing)} pass / {len(marginal)} marginal / {len(failing)} fail / {len(data)} total")
                
                if passing:
                    print("\nTop 3 passing strategies:")
                    top = sorted([(k,v) for k,v in data.items() if isinstance(v, dict) and v.get('status') == '✅'],
                               key=lambda x: x[1].get('oos', {}).get('final_capital', 0), reverse=True)[:3]
                    for k,v in top:
                        o = v.get('oos', {})
                        s = v.get('strategy', 'Unknown')
                        print(f"  {k}: {s} -> ${o.get('final_capital',0):,.0f} ({o.get('total_return_pct',0):+.1f}%) "
                              f"DD{o.get('max_drawdown_pct',0):+.1f}% PF{o.get('profit_factor',0):.2f}")
                else:
                    print("\nNo passing strategies - showing best 3 by capital:")
                    all_items = [(k,v) for k,v in data.items() if isinstance(v, dict) and 'oos' in v]
                    if all_items:
                        best = sorted(all_items, key=lambda x: x[1]['oos'].get('final_capital',0), reverse=True)[:3]
                        for k,v in best:
                            o = v['oos']; s = v.get('strategy','Unknown')
                            print(f"  {k}: {s} -> ${o.get('final_capital',0):,.0f} ({o.get('total_return_pct',0):+.1f}%) "
                                  f"DD{o.get('max_drawdown_pct',0):+.1f}% PF{o.get('profit_factor',0):.2f} [{v.get('status','?')}]")
            else:
                # Might be list of results or different format
                print(f"Data type: dict with {len(data)} keys")
                # Show first few keys
                keys = list(data.keys())[:5]
                for k in keys:
                    if isinstance(data[k], dict) and 'oos' in data[k]:
                        o = data[k]['oos']
                        print(f"  {k}: ${o.get('final_capital',0):,.0f} ({o.get('total_return_pct',0):+.1f}%) "
                              f"DD{o.get('max_drawdown_pct',0):+.1f}% PF{o.get('profit_factor',0):.2f}")
                    elif isinstance(data[k], list) and len(data[k]) > 0:
                        print(f"  {k}: list with {len(data[k])} items")
                        if isinstance(data[k][0], dict):
                            sample = data[k][0]
                            print(f"    Sample keys: {list(sample.keys())[:5]}")
        else:
            print(f"Data is not a dict: {type(data)}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    files = [
        'backtester/elder_impulse_optimize_daily_20260407_175710.json',
        'backtester/elders_impulse_multi_instrument_20260407_105201.json',
        'backtester/elders_impulse_multi_instrument.json'
    ]
    for f in files:
        check_file(f)