"""Optimize Elder's Impulse on XAU_USD — grid search across parameter space."""
import sys
import itertools
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path

WORKSPACE = Path("/Users/lich/.openclaw/workspace")
CODER_DIR = Path("/Users/lich/.openclaw/workspace-coder")
sys.path.insert(0, str(CODER_DIR))
sys.path.insert(0, str(WORKSPACE))

from data.fetcher import get_real_data
from importlib.util import spec_from_file_location, module_from_spec

strat_path = WORKSPACE / "strategies" / "strategy_elders_impulse.py"
mod = module_from_spec(spec_from_file_location("strat_mod", strat_path))
spec_from_file_location("strat_mod", strat_path).loader.exec_module(mod)
strategy_fn = mod.strategy_elders_impulse


def calculate_metrics(df, signals):
    returns = df['close'].pct_change().shift(-1)
    strategy_returns = signals * returns
    active_returns = strategy_returns[signals != 0]

    if len(active_returns.dropna()) == 0:
        return {'total_return': 0.0, 'annual_return': 0.0, 'sharpe': -999.0,
                'win_rate': 0.0, 'trades': 0, 'max_dd': 0.0}

    ret_filled = strategy_returns.fillna(0)
    cum_returns = (1 + ret_filled).cumprod()
    total_return = cum_returns.iloc[-1] - 1

    bars_per_year = 252 * 6
    n_bars = len(df)
    annual_return = (1 + total_return) ** (bars_per_year / n_bars) - 1

    daily_returns = ret_filled.resample('D').sum()
    sharpe = daily_returns.mean() / (daily_returns.std() + 1e-9) * np.sqrt(252)

    active_clean = active_returns.dropna()
    win_rate = (active_clean > 0).sum() / len(active_clean) if len(active_clean) > 0 else 0.0

    peak = cum_returns.expanding().max()
    dd = (cum_returns - peak) / peak
    max_dd = dd.min()

    pos_changes = (signals.diff().fillna(0) != 0).sum()
    trades = int(pos_changes // 2)

    return {
        'total_return': round(float(total_return) * 100, 2),
        'annual_return': round(float(annual_return) * 100, 2),
        'sharpe': round(float(sharpe), 3),
        'win_rate': round(float(win_rate) * 100, 1),
        'trades': trades,
        'max_dd': round(float(max_dd) * 100, 2),
    }


def main():
    print("=" * 80)
    print("OPTIMIZE: Elder's Impulse on XAU_USD H4 — Grid Search")
    print("=" * 80)

    # Fetch data
    df = get_real_data("XAU_USD", "H4", 400, use_cache=True)
    print(f"Loaded {len(df)} bars: {df.index[0]} → {df.index[-1]}")

    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']

    # Parameter grid
    ema_periods = [9, 13, 17, 21]
    macd_fast_vals = [8, 12, 16]
    macd_slow_vals = [20, 26, 34]
    macd_signal_vals = [6, 9, 12]

    results = []
    total_combos = len(ema_periods) * len(macd_fast_vals) * len(macd_slow_vals) * len(macd_signal_vals)
    print(f"Testing {total_combos} parameter combinations...\n")

    for ema_p, macd_f, macd_s, macd_sig in itertools.product(
            ema_periods, macd_fast_vals, macd_slow_vals, macd_signal_vals):

        if macd_f >= macd_s:
            continue

        try:
            signals = strategy_fn(
                close, high, low, volume,
                ema_period=ema_p,
                macd_fast=macd_f,
                macd_slow=macd_s,
                macd_signal=macd_sig,
            )
            metrics = calculate_metrics(df, signals)
            results.append({
                'ema_period': ema_p,
                'macd_fast': macd_f,
                'macd_slow': macd_s,
                'macd_signal': macd_sig,
                **metrics
            })
            status = "✅" if metrics['sharpe'] > 0.3 else "⚠️" if metrics['sharpe'] > 0 else "❌"
            print(f"  {status} EMA={ema_p}, MACD({macd_f},{macd_s},{macd_sig}) → "
                  f"Sharpe {metrics['sharpe']:+.3f} | Ret {metrics['total_return']:+.2f}% | "
                  f"DD {metrics['max_dd']:.2f}% | WR {metrics['win_rate']:.1f}% | Trades {metrics['trades']}")
        except Exception as e:
            print(f"  ❌ EMA={ema_p}, MACD({macd_f},{macd_s},{macd_sig}) → Error: {e}")

    if not results:
        print("No results!")
        return

    df_results = pd.DataFrame(results)

    # Top by Sharpe
    top_sharpe = df_results.nlargest(5, 'sharpe')
    print(f"\n{'=' * 80}")
    print("TOP 5 by Sharpe:")
    print(top_sharpe[['ema_period', 'macd_fast', 'macd_slow', 'macd_signal',
                       'sharpe', 'total_return', 'max_dd', 'win_rate', 'trades']].to_string(index=False))

    # Top by Sharpe with max_dd < 15%
    good_dd = df_results[df_results['max_dd'] >= -15.0]
    if len(good_dd) > 0:
        top_stable = good_dd.nlargest(5, 'sharpe')
        print(f"\n{'=' * 80}")
        print("TOP 5 by Sharpe with Max DD < 15%:")
        print(top_stable[['ema_period', 'macd_fast', 'macd_slow', 'macd_signal',
                          'sharpe', 'total_return', 'max_dd', 'win_rate', 'trades']].to_string(index=False))
        best_row = top_stable.iloc[0]
    else:
        best_row = top_sharpe.iloc[0]

    print(f"\n{'=' * 80}")
    print(f"BEST PARAMS: EMA={int(best_row['ema_period'])}, "
          f"MACD({int(best_row['macd_fast'])},{int(best_row['macd_slow'])},{int(best_row['macd_signal'])})")
    print(f"  Sharpe: {best_row['sharpe']:.3f}")
    print(f"  Return: {best_row['total_return']:.2f}%")
    print(f"  Max DD: {best_row['max_dd']:.2f}%")
    print(f"  Win Rate: {best_row['win_rate']:.1f}%")
    print(f"  Trades: {int(best_row['trades'])}")

    # Save full results
    out_dir = WORKSPACE / "backtester"
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"elders_xau_optimize_{timestamp}.json"

    import json
    output = {
        "strategy": "Elder's Impulse System",
        "instrument": "XAU_USD",
        "timeframe": "H4",
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "best_params": {
            "ema_period": int(best_row['ema_period']),
            "macd_fast": int(best_row['macd_fast']),
            "macd_slow": int(best_row['macd_slow']),
            "macd_signal": int(best_row['macd_signal']),
            "sharpe": float(best_row['sharpe']),
            "total_return": float(best_row['total_return']),
            "max_dd": float(best_row['max_dd']),
            "win_rate": float(best_row['win_rate']),
            "trades": int(best_row['trades']),
        },
        "top5_sharpe": top_sharpe[['ema_period', 'macd_fast', 'macd_slow', 'macd_signal',
                                    'sharpe', 'total_return', 'max_dd', 'win_rate', 'trades']].to_dict('records'),
        "all_results": df_results.to_dict('records'),
    }
    out_path.write_text(json.dumps(output, indent=2))
    stable_path = out_dir / "elders_xau_optimize.json"
    stable_path.write_text(json.dumps(output, indent=2))
    print(f"\nResults saved: {out_path}")


if __name__ == "__main__":
    main()
