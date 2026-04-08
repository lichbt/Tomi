#!/usr/bin/env python3
import json

print("=== Checking Elder's Impulse Results ===\n")

# Check the daily optimization file
try:
    with open('/Users/lich/.openclaw/workspace/backtester/elder_impulse_optimize_daily_20260407_175710.json') as f:
        data = json.load(f)
    
    print("File: elder_impulse_optimize_daily_20260407_175710.json")
    print("Instruments:", list(data.keys()))
    print()
    
    # Check first few instruments for best_oos
    for inst in list(data.keys())[:3]:
        if inst in data and isinstance(data[inst], dict):
            best_oos = data[inst].get('best_oos', {})
            if best_oos:
                print("{} best_oos:".format(inst))
                for k in ['total_return_pct', 'max_drawdown_pct', 'profit_factor', 'win_rate_pct', 'num_trades']:
                    if k in best_oos:
                        print("  {}: {}".format(k, best_oos[k]))
                print()
except Exception as e:
    print("Error reading daily opt file:", e)

print()

# Check multi-instrument results
try:
    with open('/Users/lich/.openclaw/workspace/backtester/elders_impulse_multi_instrument_20260407_105201.json') as f:
        data = json.load(f)
    
    print("File: elders_impulse_multi_instrument_20260407_105201.json")
    print("Type:", type(data))
    if isinstance(data, dict):
        print("Instruments:", list(data.keys()))
        print()
        
        # Check each instrument
        for inst, inst_data in data.items():
            if isinstance(inst_data, dict):
                status = inst_data.get('status', 'NO_STATUS')
                print("{}: status = {}".format(inst, status))
                # Look for performance metrics
                for field in ['final_capital', 'total_return_pct', 'max_drawdown_pct', 'profit_factor']:
                    if field in inst_data:
                        print("  {}: {}".format(field, inst_data[field]))
                if 'best_oos' in inst_data and isinstance(inst_data['best_oos'], dict):
                    oos = inst_data['best_oos']
                    for field in ['total_return_pct', 'max_drawdown_pct', 'profit_factor']:
                        if field in oos:
                            print("  oos_{}: {}".format(field, oos[field]))
                print()
except Exception as e:
    print("Error reading multi-instrument file:", e)

print()
print("=== Summary ===")
print("Elder's Impulse was tested and optimized.")
print("Results show mixed performance with some instruments showing high returns but also high drawdown.")
print("The strategy appears to be trend-following/momentum based.")