#!/usr/bin/env python3
"""
Validate 4 new mean reversion strategies across all H4 instruments.
"""
import pandas as pd
import numpy as np
import json
from datetime import datetime
import sys
import os

sys.path.insert(0, '/Users/lich/.openclaw/workspace')

from shared.strategies.strategy_cointegration_pairs import strategy_cointegration_pairs
from shared.strategies.strategy_kalman_mean_reversion import strategy_kalman_mean_reversion
from shared.strategies.strategy_rsi2_connors import strategy_rsi2_connors
from shared.strategies.strategy_atr_scaled_mean_reversion import strategy_atr_scaled_mean_reversion


CACHE_DIR = '/Users/lich/.openclaw/workspace/data/cache'
RESULTS_DIR = '/Users/lich/.openclaw/workspace/shared/backtests'

INSTRUMENTS = [
    'AUD_JPY', 'AUD_USD', 'BCO_USD', 'BTC_USD', 'ETH_USD',
    'EUR_GBP', 'EUR_JPY', 'EUR_USD', 'GBP_JPY', 'GBP_USD',
    'NAS100_USD', 'NATGAS_USD', 'NZD_USD', 'USD_CAD', 'USD_CHF',
    'USD_TRY', 'XAG_USD', 'XAU_USD'
]

# Costs
SPREAD_PCT = 0.0002  # 2 pips approx for most pairs
COMMISSION = 0

def load_data(instrument):
    """Load H4 data for instrument."""
    path = f"{CACHE_DIR}/{instrument}_H4.parquet"
    if not os.path.exists(path):
        # Try Daily
        path = f"{CACHE_DIR}/{instrument}_D.parquet"
        if not os.path.exists(path):
            return None
    df = pd.read_parquet(path)
    return df

def backtest(signals, df, initial_capital=10000, commission=COMMISSION, spread_pct=SPREAD_PCT):
    """Run backtest on signals."""
    if signals is None or len(signals) == 0:
        return None
    
    df = df.copy()
    df['signal'] = signals.values
    
    # Calculate returns
    df['returns'] = df['close'].pct_change().fillna(0)
    
    # Strategy returns (accounting for spread on entry/exit)
    df['position'] = df['signal'].shift(1).fillna(0)
    df['strategy_returns'] = df['position'] * df['returns']
    
    # Deduct spread on trade entry/exit
    trades = (df['signal'].diff() != 0).sum()
    spread_cost = trades * spread_pct / 2  # Approximate
    df['strategy_returns'] -= spread_cost / len(df)
    
    # Cumulative returns
    df['cumulative'] = (1 + df['strategy_returns']).cumprod()
    df['equity'] = initial_capital * df['cumulative']
    
    # Calculate metrics
    total_return = (df['equity'].iloc[-1] / initial_capital - 1) * 100
    n_periods = len(df)
    annual_return = ((1 + total_return/100) ** (365*6/n_periods) - 1) * 100  # H4 = 6x per day
    
    # Volatility and Sharpe
    annual_vol = df['strategy_returns'].std() * np.sqrt(365*6)
    sharpe = annual_return / annual_vol if annual_vol > 0 else 0
    
    # Max drawdown
    df['peak'] = df['equity'].cummax()
    df['drawdown'] = (df['equity'] - df['peak']) / df['peak']
    max_dd = df['drawdown'].min() * 100
    
    # Trade analysis
    position_changes = df['signal'].diff()
    n_trades = (position_changes != 0).sum()
    n_long = (df['signal'] == 1).sum()
    n_short = (df['signal'] == -1).sum()
    
    # Win rate
    df['trade_return'] = df['strategy_returns'] * df['position'].abs()
    winning_trades = (df['trade_return'] > 0).sum()
    win_rate = winning_trades / n_trades * 100 if n_trades > 0 else 0
    
    return {
        'total_return': round(total_return, 2),
        'annual_return': round(annual_return, 2),
        'sharpe': round(sharpe, 3),
        'max_dd': round(max_dd, 2),
        'n_trades': int(n_trades),
        'win_rate': round(win_rate, 1),
        'n_long': int(n_long),
        'n_short': int(n_short)
    }

def validate_strategy(strategy_func, instrument, strategy_name, **kwargs):
    """Validate a single strategy on an instrument."""
    df = load_data(instrument)
    if df is None:
        return None
    
    # Ensure required columns exist
    required = ['close', 'high', 'low']
    if not all(col in df.columns for col in required):
        return None
    
    try:
        # For pairs strategy, we need x and y columns
        if strategy_name == 'cointegration':
            # Create synthetic y column for pairs (use close shifted)
            df['x'] = df['close']
            df['y'] = df['close'].shift(10) + np.random.randn(len(df)) * df['close'] * 0.001
            signals = strategy_func(df, x_col='x', y_col='y', **kwargs)
        else:
            signals = strategy_func(df, **kwargs)
        
        if signals is None or len(signals) == 0:
            return None
            
        results = backtest(signals, df)
        return results
    except Exception as e:
        print(f"  ERROR: {e}")
        return None

def main():
    print("=" * 80)
    print("STRATEGY VALIDATION - H4 ALL INSTRUMENTS")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    strategies = [
        ('Cointegration Pairs', strategy_cointegration_pairs, {}),
        ('Kalman Filter MR', strategy_kalman_mean_reversion, {}),
        ('RSI(2) Connors', strategy_rsi2_connors, {}),
        ('ATR-Scaled MR', strategy_atr_scaled_mean_reversion, {}),
    ]
    
    all_results = {}
    
    for strat_name, strat_func, kwargs in strategies:
        print(f"\n{'='*80}")
        print(f"STRATEGY: {strat_name}")
        print(f"{'='*80}")
        
        results_table = []
        
        for instrument in INSTRUMENTS:
            result = validate_strategy(strat_func, instrument, strat_name, **kwargs)
            
            if result:
                status = "✅" if result['sharpe'] > 0.5 and result['n_trades'] > 20 else "⚠️" if result['n_trades'] > 10 else "❌"
                print(f"  {status} {instrument:15} | Sharpe: {result['sharpe']:+.3f} | Return: {result['total_return']:+.1f}% | DD: {result['max_dd']:+.1f}% | Trades: {result['n_trades']:3d} | Win%: {result['win_rate']:.0f}")
                
                results_table.append({
                    'instrument': instrument,
                    **result
                })
            else:
                print(f"  ❌ {instrument:15} | No data or error")
        
        if results_table:
            # Calculate summary
            df_results = pd.DataFrame(results_table)
            avg_sharpe = df_results['sharpe'].mean()
            avg_return = df_results['total_return'].mean()
            avg_dd = df_results['max_dd'].mean()
            total_trades = df_results['n_trades'].sum()
            avg_win_rate = df_results['win_rate'].mean()
            pass_count = len(df_results[df_results['sharpe'] > 0.5])
            
            print(f"\n  --- SUMMARY ---")
            print(f"  Avg Sharpe: {avg_sharpe:+.3f} | Avg Return: {avg_return:+.1f}% | Avg DD: {avg_dd:+.1f}%")
            print(f"  Total Trades: {total_trades} | Avg Win Rate: {avg_win_rate:.0f}% | Instruments Passed (Sharpe>0.5): {pass_count}/{len(df_results)}")
            
            all_results[strat_name] = {
                'results': results_table,
                'summary': {
                    'avg_sharpe': round(avg_sharpe, 3),
                    'avg_return': round(avg_return, 2),
                    'avg_dd': round(avg_dd, 2),
                    'total_trades': int(total_trades),
                    'avg_win_rate': round(avg_win_rate, 1),
                    'pass_count': pass_count
                }
            }
            
            # Save to file
            filename = f"{RESULTS_DIR}/new_strategies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(all_results, f, indent=2)
            print(f"\n  💾 Results saved to: {filename}")
    
    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)
    
    return all_results

if __name__ == '__main__':
    main()
