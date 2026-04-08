# Leverage Analysis — Portfolio v13

**Method:** Block Bootstrap Monte Carlo (10,000 sims, block size=20)

**Positions:**

- donchian: BTC_USD H4 (26.0%)
- st_vol: XAG_USD H4 (18.0%)
- ichimoku: NAS100_USD H4 (15.5%)
- adx: USD_TRY H4 (15.5%)
- volatility: BCO_USD H4 (12.8%)
- macd: XAU_USD H4 (12.2%)

**Leverage Cost:** 6.5% annual per 1x borrowed

## Results

| Leverage | Ann Return | Median DD | Worst 5% DD | Ruin % | Sharpe | Lev Cost | Net Return |
|----------|-----------|-----------|-------------|--------|--------|----------|-----------|
| 1.0x | 11.14% | -17.6% | -27.7% | 0.00% | 0.803 | 6.5% | 11.14% |
| 1.5x | 16.75% | -25.6% | -39.0% | 0.00% | 1.477 | 9.8% | 16.75% **OPTIMAL** |
| 2.0x | 21.88% | -33.1% | -49.6% | 0.00% | 1.037 | 13.0% | 21.88% |
| 3.0x | 32.09% | -46.3% | -65.5% | 0.09% | 0.737 | 19.5% | 32.09% |
| 5.0x | 48.80% | -67.5% | -85.8% | 0.32% | 1.081 | 32.5% | 48.80% |

## Recommendation

**Optimal Leverage: 1.5x** (highest risk-adjusted return, Sharpe=1.477)

**No leverage level meets safe criteria (Ruin < 5%, W5-DD > -25%).**
