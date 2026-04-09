"""Multi-strategy multi-instrument backtest runner for general tab strategies."""
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

WORKSPACE   = Path("/Users/lich/.openclaw/workspace")
SHARED_STRAT = Path("/Users/lich/.openclaw/shared/strategies")
CODER_DIR  = Path("/Users/lich/.openclaw/workspace-coder")
sys.path.insert(0, str(CODER_DIR))
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(SHARED_STRAT))

from data.fetcher import get_real_data

INSTRUMENTS = ["BTC_USD", "XAU_USD", "BCO_USD", "NAS100_USD", "XAG_USD", "USD_TRY"]
GRANULARITY = "H4"
DAYS = 400

STRATEGIES = {
    "rsi2_connors":     "strategy_rsi2_connors.py",
    "kalman_mr":        "strategy_kalman_mean_reversion.py",
    "atr_scaled":       "strategy_atr_scaled_mean_reversion.py",
    "cointegration":    "strategy_cointegration_pairs.py",
}


def load_strat(filename):
    p = SHARED_STRAT / filename
    mod = module_from_spec(spec_from_file_location("strat", p))
    spec_from_file_location("strat", p).loader.exec_module(mod)
    return mod


def calc_metrics(df, signals):
    returns = df['close'].pct_change().shift(-1)
    strat_ret = signals * returns
    active = strat_ret[signals != 0]

    if len(active.dropna()) == 0:
        return {'total_return': 0.0, 'annual_return': 0.0, 'sharpe': 0.0,
                'win_rate': 0.0, 'trades': 0, 'max_dd': 0.0}

    ret_filled = strat_ret.fillna(0)
    cum = (1 + ret_filled).cumprod()
    total_ret = cum.iloc[-1] - 1
    bars_per_year = 252 * 6
    annual = (1 + total_ret) ** (bars_per_year / len(df)) - 1
    daily = ret_filled.resample('D').sum()
    sharpe = daily.mean() / (daily.std() + 1e-9) * np.sqrt(252)
    active_c = active.dropna()
    win_rate = (active_c > 0).sum() / len(active_c) if len(active_c) > 0 else 0.0
    peak = cum.expanding().max()
    dd = (cum - peak) / peak
    max_dd = dd.min()
    pos_chg = (signals.diff().fillna(0) != 0).sum()
    trades = int(pos_chg // 2)

    return {
        'total_return': round(float(total_ret) * 100, 2),
        'annual_return': round(float(annual) * 100, 2),
        'sharpe': round(float(sharpe), 3),
        'win_rate': round(float(win_rate) * 100, 1),
        'trades': trades,
        'max_dd': round(float(max_dd) * 100, 2),
        'bar_count': int(len(df)),
    }


def run_strategy(name, strat_fn, param_override=None):
    print(f"\n{'='*60}")
    print(f"STRATEGY: {name}")
    print(f"{'='*60}")
    results = {}
    for instr in INSTRUMENTS:
        print(f"\n  --- {instr} ---")
        try:
            df = get_real_data(instr, GRANULARITY, DAYS, use_cache=True)
            print(f"    {len(df)} bars: {df.index[0].date()} → {df.index[-1].date()}")
            params = param_override if param_override else {}
            signals = strat_fn(df, **params)
            m = calc_metrics(df, signals)
            results[instr] = m
            status = "✅" if m['sharpe'] > 0.3 else "⚠️" if m['sharpe'] > 0 else "❌"
            print(f"    {status} Sharpe {m['sharpe']:+.3f} | Ret {m['total_return']:+.2f}% | "
                  f"DD {m['max_dd']:.2f}% | WR {m['win_rate']:.1f}% | Trades {m['trades']}")
        except Exception as e:
            import traceback; traceback.print_exc()
            results[instr] = {'sharpe': 0.0, 'error': str(e)}

    sh = {k: v['sharpe'] for k, v in results.items() if v.get('sharpe', 0) != 0.0}
    passing = [k for k, v in results.items() if v.get('sharpe', 0) > 0.3]
    failing = [k for k, v in results.items() if v.get('sharpe', 0) <= 0.3]
    avg_sh = round(np.mean(list(sh.values())), 3) if sh else 0.0
    best = max(sh, key=sh.get) if sh else "N/A"
    worst = min(sh, key=sh.get) if sh else "N/A"
    total_trades = sum(v.get('trades', 0) for v in results.values())

    out = {
        "strategy": name,
        "timeframe": GRANULARITY,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "results": results,
        "summary": {
            "best_instrument": best,
            "worst_instrument": worst,
            "avg_sharpe": avg_sh,
            "passing_instruments": passing,
            "failing_instruments": failing,
            "total_trades": total_trades,
        }
    }

    out_dir = WORKSPACE / "backtester"
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = name.replace(" ", "_").lower()
    out_path = out_dir / f"{safe_name}_{ts}.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    (out_dir / f"{safe_name}_latest.json").write_text(json.dumps(out, indent=2))
    print(f"\n  → Saved: {out_path}")
    return out


def main():
    strat_name = sys.argv[1] if len(sys.argv) > 1 else "all"

    if strat_name == "all":
        for sname, sfile in STRATEGIES.items():
            mod = load_strat(sfile)
            fn = getattr(mod, list(filter(lambda x: x.startswith("strategy"), dir(mod)))[0])
            run_strategy(sname, fn)
    else:
        sfile = STRATEGIES.get(strat_name)
        if not sfile:
            print(f"Unknown strategy: {strat_name}")
            print(f"Available: {list(STRATEGIES.keys())}")
            return
        mod = load_strat(sfile)
        fn = getattr(mod, list(filter(lambda x: x.startswith("strategy"), dir(mod)))[0])
        run_strategy(strat_name, fn)


if __name__ == "__main__":
    main()
