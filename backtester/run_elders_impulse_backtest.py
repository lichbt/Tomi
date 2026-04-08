"""Multi-instrument backtest for Elder's Impulse strategy."""
import sys
import os
import json
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path

# Add paths for imports
WORKSPACE = Path("/Users/lich/.openclaw/workspace")
CODER_DIR = Path("/Users/lich/.openclaw/workspace-coder")
sys.path.insert(0, str(CODER_DIR))
sys.path.insert(0, str(WORKSPACE))

from data.fetcher import get_real_data
from importlib.util import spec_from_file_location, module_from_spec

INSTRUMENTS = ["BTC_USD", "XAU_USD", "BCO_USD", "USD_TRY", "NAS100_USD", "XAG_USD"]
GRANULARITY = "H4"
DAYS = 400

# Load strategy module
strat_path = WORKSPACE / "strategies" / "strategy_elders_impulse.py"
mod = module_from_spec(spec_from_file_location("strat_mod", strat_path))
spec_from_file_location("strat_mod", strat_path).loader.exec_module(mod)
strategy_fn = mod.strategy_elders_impulse


def calculate_metrics(df, signals):
    returns = df['close'].pct_change().shift(-1)
    strategy_returns = signals * returns
    active_returns = strategy_returns[signals != 0]

    if len(active_returns.dropna()) == 0:
        return {
            'total_return': 0.0, 'annual_return': 0.0, 'sharpe': 0.0,
            'win_rate': 0.0, 'trades': 0, 'max_dd': 0.0
        }

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

    # Count distinct trades (position transitions: 0→1, 0→-1, 1→0, -1→0)
    pos_changes = (signals.diff().fillna(0) != 0).sum()

    return {
        'total_return': round(float(total_return) * 100, 2),
        'annual_return': round(float(annual_return) * 100, 2),
        'sharpe': round(float(sharpe), 3),
        'win_rate': round(float(win_rate) * 100, 1),
        'trades': int(pos_changes // 2),
        'max_dd': round(float(max_dd) * 100, 2),
        'bar_count': int(n_bars),
    }


def main():
    print("=" * 80)
    print("BACKTEST: Elder's Impulse System — Multi-Instrument H4")
    print("=" * 80)

    results = {}
    errors = []

    for instrument in INSTRUMENTS:
        print(f"\n--- {instrument} ---")
        try:
            df = get_real_data(instrument=instrument, granularity=GRANULARITY, days=DAYS, use_cache=True)
            close = df['close']
            high = df['high']
            low = df['low']
            volume = df['volume']
            print(f"  Fetched {len(df)} bars, range: {df.index[0]} → {df.index[-1]}")

            signals = strategy_fn(close, high, low, volume)
            metrics = calculate_metrics(df, signals)
            results[instrument] = metrics

            status = "✅" if metrics['sharpe'] > 0.3 else "⚠️" if metrics['sharpe'] > 0 else "❌"
            print(f"  {status} Sharpe: {metrics['sharpe']:.3f} | Return: {metrics['total_return']:.2f}% | "
                  f"Trades: {metrics['trades']} | Max DD: {metrics['max_dd']:.2f}% | "
                  f"Win Rate: {metrics['win_rate']:.1f}%")

        except Exception as e:
            print(f"  ❌ Error: {e}")
            errors.append({"instrument": instrument, "error": str(e)})
            results[instrument] = {
                'total_return': 0.0, 'annual_return': 0.0, 'sharpe': 0.0,
                'win_rate': 0.0, 'trades': 0, 'max_dd': 0.0, 'error': str(e)
            }

    sharpe_values = {k: v['sharpe'] for k, v in results.items() if v['sharpe'] != 0.0}
    winrate_values = {k: v['win_rate'] for k, v in results.items() if v.get('trades', 0) > 0}
    total_trades = sum(v.get('trades', 0) for v in results.values())

    if sharpe_values:
        best_inst = max(sharpe_values, key=sharpe_values.get)
        worst_inst = min(sharpe_values, key=sharpe_values.get)
    else:
        best_inst = "N/A"
        worst_inst = "N/A"

    avg_sharpe = round(np.mean(list(sharpe_values.values())), 3) if sharpe_values else 0.0
    avg_winrate = round(np.mean(list(winrate_values.values())), 1) if winrate_values else 0.0
    passing = [k for k, v in results.items() if v.get('sharpe', 0) > 0.3]
    failing = [k for k, v in results.items() if v.get('sharpe', 0) <= 0.3]

    output = {
        "strategy": "Elder's Impulse System",
        "timeframe": "H4",
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "results": results,
        "summary": {
            "best_instrument": best_inst,
            "worst_instrument": worst_inst,
            "avg_sharpe": avg_sharpe,
            "avg_win_rate": avg_winrate,
            "total_trades": total_trades,
            "passing_instruments": passing,
            "failing_instruments": failing
        },
        "errors": errors
    }

    out_dir = WORKSPACE / "backtester"
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"elders_impulse_multi_instrument_{timestamp}.json"
    out_path.write_text(json.dumps(output, indent=2))

    stable_path = out_dir / "elders_impulse_multi_instrument.json"
    stable_path.write_text(json.dumps(output, indent=2))

    print(f"\n{'=' * 80}")
    print(f"RESULTS SAVED: {out_path}")
    print(f"{'=' * 80}")
    print(f"Best:  {best_inst}")
    print(f"Worst: {worst_inst}")
    print(f"Avg Sharpe: {avg_sharpe}")
    print(f"Passing: {passing}")
    print(f"Failing: {failing}")

    return output


if __name__ == "__main__":
    main()
