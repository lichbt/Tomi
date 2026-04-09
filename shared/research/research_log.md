# SHARED Research Log — Unified Pipeline Tracking

## Master Dashboard

**FULL OPTIMIZATION COMPLETED** — 6 strategies × 2 timeframes (H4 + Daily) × 6 instruments
IS: 2015-2019 | OOS: 2020-2025 | Methodology: Corrected (entry OPEN, intra-candle stops, Kelly two-pass 0.08-1.0%, spread costs)
File: `backtester/full_optimize_20260408_215841.json`

---

## Results Summary

### H4 Timeframe

| Strategy | Pass | Marginal | Fail | Best OOS | Best Instr |
|---|---|---|---|---|---|
| **Elder's Impulse** | 5 | 0 | 1 (USD_TRY) | **+44.0%** | XAG_USD |
| **Volatility Expansion** | 6 | 0 | 0 | **+34.7%** | XAG_USD |
| **ADX Trend** | 6 | 0 | 0 | **+12.7%** | XAG_USD |
| **Ichimoku Cloud** | 6 | 0 | 0 | **+9.8%** | XAG_USD |
| **MACD Momentum** | 5 | 0 | 1 (USD_TRY) | **+7.2%** | XAG_USD |
| **Supertrend+Vol** | 4 | 1 (XAU) | 1 (USD_TRY) | **+2.6%** | NAS100_USD |

### Daily Timeframe

| Strategy | Pass | Marginal | Fail | Best OOS | Best Instr |
|---|---|---|---|---|---|
| **Elder's Impulse** | 5 | 0 | 0 | **+10.9%** | NAS100_USD |
| **Volatility Expansion** | 5 | 0 | 0 | **+7.7%** | XAU_USD |
| **ADX Trend** | 5 | 0 | 0 | **+3.6%** | XAU_USD |
| **Ichimoku Cloud** | 5 | 0 | 0 | **+4.5%** | USD_TRY |
| **MACD Momentum** | 5 | 0 | 0 | **+2.6%** | XAG_USD |
| **Supertrend+Vol** | 3 | 1 (XAG) | 1 (USD_TRY) | **+2.0%** | XAU_USD |

---

## Full Results Table

### H4 — Elder's Impulse
| Instrument | Status | IS$ | OOS$ | OOS% | DD% | PF | WR% | Trades | Kelly% | Best Params |
|---|---|---|---|---|---|---|---|---|---|---|
| XAG_USD | ✅ PASS | $14,734 | $14,395 | +44.0% | -0.2% | 7.57 | 69% | 2,184 | 1.00% | ema=7,macd_f=8,macd_s=26,sig=7,atr=1.5 |
| XAU_USD | ✅ PASS | $10,599 | $12,452 | +24.5% | -0.1% | 8.48 | 69% | 2,187 | 1.00% | ema=7,macd_f=8,macd_s=26,sig=7,atr=2.5 |
| NAS100_USD | ✅ PASS | $10,428 | $12,231 | +22.3% | -0.1% | 8.02 | 76% | 2,119 | 1.00% | ema=7,macd_f=8,macd_s=21,sig=7,atr=3.0 |
| BCO_USD | ✅ PASS | $11,020 | $11,627 | +16.3% | -0.1% | 8.06 | 69% | 2,194 | 1.00% | ema=7,macd_f=8,macd_s=26,sig=7,atr=3.0 |
| BTC_USD | ✅ PASS | $10,223 | $11,479 | +14.8% | -0.1% | 7.80 | 71% | 2,174 | 1.00% | ema=7,macd_f=8,macd_s=21,sig=7,atr=3.0 |
| USD_TRY | ❌ FAIL | $43,182 | $9,602 | -4.0% | -20.4% | 4.36 | 35% | 1,958 | 1.00% | ema=7,macd_f=8,macd_s=21,sig=7,atr=1.5 |

### H4 — Volatility Expansion
| Instrument | Status | IS$ | OOS$ | OOS% | DD% | PF | WR% | Trades | Kelly% | Best Params |
|---|---|---|---|---|---|---|---|---|---|---|
| XAG_USD | ✅ PASS | $13,638 | $13,468 | +34.7% | -0.1% | 9.39 | 74% | 1,531 | 1.00% | lb=14,vm=1.0,atr=1.5 |
| USD_TRY | ✅ PASS | $39,736 | $12,600 | +26.0% | -2.3% | 9.45 | 52% | 889 | 1.00% | lb=30,vm=1.5,atr=2.0 |
| XAU_USD | ✅ PASS | $10,508 | $11,888 | +18.9% | -0.2% | 8.75 | 75% | 1,537 | 1.00% | lb=14,vm=1.0,atr=1.5 |
| NAS100_USD | ✅ PASS | $10,349 | $11,749 | +17.5% | -0.1% | 8.10 | 78% | 1,528 | 1.00% | lb=14,vm=1.0,atr=1.5 |
| BTC_USD | ✅ PASS | $10,188 | $11,208 | +12.1% | -0.0% | 13.87 | 78% | 1,516 | 1.00% | lb=14,vm=1.0,atr=1.5 |
| BCO_USD | ✅ PASS | $10,815 | $11,050 | +10.5% | -0.0% | 20.35 | 80% | 984 | 1.00% | lb=30,vm=1.0,atr=1.5 |

### H4 — ADX Trend
| Instrument | Status | IS$ | OOS$ | OOS% | DD% | PF | WR% | Trades | Kelly% | Best Params |
|---|---|---|---|---|---|---|---|---|---|---|
| XAG_USD | ✅ PASS | $10,791 | $11,269 | +12.7% | -0.2% | 4.28 | 58% | 840 | 1.00% | adx_p=7,adx_t=20,ema=20,atr=3.0 |
| XAU_USD | ✅ PASS | $10,184 | $10,945 | +9.4% | -0.2% | 5.17 | 60% | 816 | 1.00% | adx_p=7,adx_t=20,ema=50,atr=3.0 |
| NAS100_USD | ✅ PASS | $10,160 | $10,753 | +7.5% | -0.1% | 3.88 | 61% | 827 | 1.00% | adx_p=7,adx_t=20,ema=100,atr=2.0 |
| BTC_USD | ✅ PASS | $10,090 | $10,473 | +4.7% | -0.2% | 3.14 | 57% | 834 | 1.00% | adx_p=7,adx_t=20,ema=50,atr=3.0 |
| BCO_USD | ✅ PASS | $10,248 | $10,349 | +3.5% | -0.1% | 4.69 | 58% | 623 | 1.00% | adx_p=14,adx_t=20,ema=100,atr=2.5 |
| USD_TRY | ✅ PASS | $14,741 | $10,267 | +2.7% | -3.9% | 3.71 | 33% | 654 | 1.00% | adx_p=7,adx_t=30,ema=20,atr=1.5 |

### H4 — Ichimoku Cloud
| Instrument | Status | IS$ | OOS$ | OOS% | DD% | PF | WR% | Trades | Kelly% | Best Params |
|---|---|---|---|---|---|---|---|---|---|---|
| XAG_USD | ✅ PASS | $10,617 | $10,983 | +9.8% | -0.1% | 5.86 | 63% | 420 | 1.00% | t=7,k=22,s=44,atr=1.5 |
| XAU_USD | ✅ PASS | $10,124 | $10,576 | +5.8% | -0.2% | 3.85 | 55% | 427 | 1.00% | t=7,k=22,s=44,atr=2.5 |
| USD_TRY | ✅ PASS | $13,216 | $10,540 | +5.4% | -1.6% | 4.42 | 37% | 381 | 1.00% | t=7,k=26,s=52,atr=2.5 |
| NAS100_USD | ✅ PASS | $10,090 | $10,460 | +4.6% | -0.1% | 3.65 | 58% | 437 | 1.00% | t=7,k=26,s=44,atr=1.5 |
| BTC_USD | ✅ PASS | $10,063 | $10,355 | +3.5% | -0.1% | 3.82 | 56% | 413 | 1.00% | t=7,k=22,s=52,atr=2.0 |
| BCO_USD | ✅ PASS | $10,154 | $10,274 | +2.7% | -0.2% | 2.95 | 53% | 441 | 1.00% | t=7,k=26,s=52,atr=2.0 |

### H4 — MACD Momentum
| Instrument | Status | IS$ | OOS$ | OOS% | DD% | PF | WR% | Trades | Kelly% | Best Params |
|---|---|---|---|---|---|---|---|---|---|---|
| XAG_USD | ✅ PASS | $10,869 | $10,724 | +7.2% | -0.2% | 4.32 | 60% | 468 | 1.00% | f=12,s=26,sig=9,atr=1.5 |
| XAU_USD | ✅ PASS | $10,201 | $10,629 | +6.3% | -0.2% | 4.19 | 56% | 479 | 1.00% | f=12,s=34,sig=7,atr=2.0 |
| NAS100_USD | ✅ PASS | $10,076 | $10,411 | +4.1% | -0.1% | 4.11 | 59% | 525 | 1.00% | f=12,s=21,sig=7,atr=2.0 |
| BCO_USD | ✅ PASS | $10,223 | $10,320 | +3.2% | -0.2% | 4.25 | 57% | 532 | 1.00% | f=8,s=26,sig=7,atr=2.0 |
| BTC_USD | ✅ PASS | $10,062 | $10,313 | +3.1% | -0.1% | 4.36 | 59% | 492 | 1.00% | f=12,s=21,sig=7,atr=2.0 |
| USD_TRY | ❌ FAIL | $14,008 | $9,831 | -1.7% | -7.9% | 3.40 | 32% | 542 | 1.00% | f=12,s=26,sig=7,atr=1.5 |

### H4 — Supertrend+Vol
| Instrument | Status | IS$ | OOS$ | OOS% | DD% | PF | WR% | Trades | Kelly% | Best Params |
|---|---|---|---|---|---|---|---|---|---|---|
| NAS100_USD | ✅ PASS | $10,052 | $10,264 | +2.6% | -0.2% | 1.79 | 53% | 1,345 | 1.00% | st_p=7,st_m=2.0,atr=2.0 |
| BTC_USD | ✅ PASS | $10,034 | $10,216 | +2.2% | -0.4% | 1.79 | 51% | 1,713 | 1.00% | st_p=7,st_m=2.0,atr=2.5 |
| BCO_USD | ✅ PASS | $10,042 | $10,148 | +1.5% | -0.4% | 1.93 | 49% | 1,528 | 1.00% | st_p=7,st_m=2.0,atr=2.0 |
| XAG_USD | ✅ PASS | $9,790 | $10,108 | +1.1% | -0.7% | 1.55 | 50% | 1,638 | 1.00% | st_p=7,st_m=2.0,atr=1.5 |
| XAU_USD | ⚠️ MARGINAL | $10,020 | $10,018 | +0.2% | -1.3% | 1.51 | 48% | 1,634 | 1.00% | st_p=7,st_m=2.0,atr=2.5 |
| USD_TRY | ❌ FAIL | $7,505 | $7,922 | -20.8% | -20.8% | 1.32 | 22% | 1,492 | 1.00% | st_p=7,st_m=2.0,atr=1.5 |

### Daily — Elder's Impulse
| Instrument | Status | IS$ | OOS$ | OOS% | DD% | PF | WR% | Trades | Kelly% | Best Params |
|---|---|---|---|---|---|---|---|---|---|---|
| NAS100_USD | ✅ PASS | $10,243 | $11,089 | +10.9% | -0.1% | 9.37 | 78% | 406 | 1.00% | ema=7,macd_f=8,macd_s=21,sig=7,atr=3.0 |
| XAU_USD | ✅ PASS | $10,345 | $11,038 | +10.4% | -0.2% | 7.57 | 77% | 343 | 1.00% | ema=7,macd_f=8,macd_s=26,sig=7,atr=2.5 |
| USD_TRY | ✅ PASS | $15,150 | $10,838 | +8.4% | -0.8% | 7.41 | 52% | 307 | 1.00% | ema=7,macd_f=8,macd_s=21,sig=7,atr=1.5 |
| XAG_USD | ✅ PASS | $10,840 | $10,724 | +7.2% | -0.2% | 7.24 | 70% | 359 | 1.00% | ema=7,macd_f=8,macd_s=26,sig=7,atr=1.5 |
| BCO_USD | ✅ PASS | $10,429 | $10,715 | +7.2% | -0.1% | 10.02 | 75% | 388 | 1.00% | ema=13,macd_f=8,macd_s=26,sig=7,atr=2.5 |

### Daily — Volatility Expansion
| Instrument | Status | IS$ | OOS$ | OOS% | DD% | PF | WR% | Trades | Kelly% | Best Params |
|---|---|---|---|---|---|---|---|---|---|---|
| XAU_USD | ✅ PASS | $10,289 | $10,770 | +7.7% | -0.1% | 11.21 | 75% | 245 | 1.00% | lb=14,vm=1.0,atr=1.5 |
| NAS100_USD | ✅ PASS | $10,159 | $10,635 | +6.3% | -0.2% | 8.72 | 82% | 227 | 1.00% | lb=14,vm=1.0,atr=1.5 |
| XAG_USD | ✅ PASS | $10,883 | $10,630 | +6.3% | -0.1% | 11.96 | 81% | 251 | 1.00% | lb=14,vm=1.0,atr=1.5 |
| USD_TRY | ✅ PASS | $13,860 | $10,565 | +5.7% | -0.3% | 6.46 | 61% | 159 | 1.00% | lb=30,vm=1.5,atr=2.0 |
| BCO_USD | ✅ PASS | $10,272 | $10,550 | +5.5% | -0.1% | 10.25 | 81% | 238 | 1.00% | lb=14,vm=1.0,atr=1.5 |

### Daily — ADX Trend
| Instrument | Status | IS$ | OOS$ | OOS% | DD% | PF | WR% | Trades | Kelly% | Best Params |
|---|---|---|---|---|---|---|---|---|---|---|
| XAU_USD | ✅ PASS | $10,105 | $10,362 | +3.6% | -0.3% | 2.78 | 58% | 155 | 1.00% | adx_p=7,adx_t=20,ema=20,atr=3.0 |
| USD_TRY | ✅ PASS | $11,574 | $10,259 | +2.6% | -0.4% | 4.51 | 61% | 71 | 1.00% | adx_p=7,adx_t=30,ema=20,atr=1.5 |
| NAS100_USD | ✅ PASS | $10,064 | $10,239 | +2.4% | -0.1% | 6.97 | 72% | 90 | 1.00% | adx_p=7,adx_t=20,ema=100,atr=1.5 |
| XAG_USD | ✅ PASS | $10,217 | $10,223 | +2.2% | -0.1% | 7.64 | 69% | 102 | 1.00% | adx_p=7,adx_t=20,ema=100,atr=1.5 |
| BCO_USD | ✅ PASS | $10,124 | $10,151 | +1.5% | -0.3% | 3.35 | 63% | 101 | 1.00% | adx_p=7,adx_t=20,ema=100,atr=3.0 |

### Daily — Ichimoku Cloud
| Instrument | Status | IS$ | OOS$ | OOS% | DD% | PF | WR% | Trades | Kelly% | Best Params |
|---|---|---|---|---|---|---|---|---|---|---|
| USD_TRY | ✅ PASS | $10,911 | $10,449 | +4.5% | -0.1% | 30.25 | 70% | 37 | 1.00% | t=7,k=22,s=44,atr=3.0 |
| XAU_USD | ✅ PASS | $10,079 | $10,326 | +3.3% | -0.3% | 4.21 | 51% | 76 | 1.00% | t=7,k=22,s=44,atr=2.5 |
| BCO_USD | ✅ PASS | $10,093 | $10,159 | +1.6% | -0.1% | 4.15 | 58% | 78 | 1.00% | t=7,k=22,s=44,atr=3.0 |
| NAS100_USD | ✅ PASS | $10,061 | $10,125 | +1.2% | -0.2% | 2.98 | 63% | 70 | 1.00% | t=7,k=26,s=52,atr=1.5 |
| XAG_USD | ✅ PASS | $10,137 | $10,114 | +1.1% | -0.1% | 5.22 | 56% | 69 | 1.00% | t=7,k=26,s=44,atr=2.5 |

### Daily — MACD Momentum
| Instrument | Status | IS$ | OOS$ | OOS% | DD% | PF | WR% | Trades | Kelly% | Best Params |
|---|---|---|---|---|---|---|---|---|---|---|
| XAG_USD | ✅ PASS | $10,229 | $10,263 | +2.6% | -0.1% | 10.97 | 68% | 73 | 1.00% | f=8,s=26,sig=7,atr=1.5 |
| USD_TRY | ✅ PASS | $11,122 | $10,258 | +2.6% | -0.4% | 4.45 | 44% | 81 | 1.00% | f=12,s=21,sig=7,atr=2.0 |
| XAU_USD | ✅ PASS | $10,091 | $10,209 | +2.1% | -0.4% | 3.24 | 56% | 84 | 1.00% | f=8,s=21,sig=7,atr=2.0 |
| NAS100_USD | ✅ PASS | $10,058 | $10,140 | +1.4% | -0.2% | 3.25 | 54% | 90 | 1.00% | f=8,s=21,sig=7,atr=1.5 |
| BCO_USD | ✅ PASS | $10,094 | $10,110 | +1.1% | -0.4% | 2.34 | 56% | 72 | 1.00% | f=8,s=21,sig=7,atr=2.5 |

### Daily — Supertrend+Vol
| Instrument | Status | IS$ | OOS$ | OOS% | DD% | PF | WR% | Trades | Kelly% | Best Params |
|---|---|---|---|---|---|---|---|---|---|---|
| XAU_USD | ✅ PASS | $10,085 | $10,205 | +2.0% | -0.6% | 1.89 | 56% | 285 | 1.00% | st_p=7,st_m=2.0,atr=2.5 |
| NAS100_USD | ✅ PASS | $10,034 | $10,092 | +0.9% | -0.7% | 1.44 | 52% | 249 | 1.00% | st_p=7,st_m=2.0,atr=2.5 |
| BCO_USD | ✅ PASS | $10,047 | $10,042 | +0.4% | -0.5% | 1.37 | 48% | 263 | 1.00% | st_p=7,st_m=4.0,atr=2.5 |
| XAG_USD | ⚠️ MARGINAL | $10,097 | $10,014 | +0.1% | -0.3% | 1.21 | 51% | 277 | 1.00% | st_p=7,st_m=2.0,atr=1.5 |
| USD_TRY | ❌ FAIL | $9,984 | $9,908 | -0.9% | -1.5% | 1.34 | 34% | 287 | 1.00% | st_p=7,st_m=2.0,atr=1.5 |

---

## Strategies Not Passing

| Strategy | Instr | TF | Reason |
|---|---|---|---|
| Supertrend+Vol | XAU_USD | H4 | Sharpe too low (DD -1.3%, marginal) |
| Supertrend+Vol | XAG_USD | Daily | Marginal (DD -0.3%, barely positive) |
| Supertrend+Vol | USD_TRY | Both | Regime collapse, high DD, negative return |
| Elder's Impulse | USD_TRY | H4 | Regime collapse (-4% OOS, -20% DD) |
| MACD Momentum | USD_TRY | H4 | Regime collapse (-1.7% OOS, -7.9% DD) |

---

## Rejected Strategies (Prior Backtests)
| Strategy | Timeframe | Reason |
|---|---|---|
| FRAMA | Daily | All combos lost (PF < 1.0, DD > 96%) |
| Choppiness Index MR | Daily | All combos lost (PF < 1.0, DD > 96%) |

---

## General Tab Strategy Backtests (2026-04-08)
| Strategy | Status | Pass | Marginal | Fail | Best Instr | Best Sharpe |
|---|---|---|---|---|---|---|
| RSI(2) Connors | ✅ Validated | 5/6 | 0 | 1 | XAU_USD | 0.590 |
| Kalman MR (ATR-stop v3) | ✅ Validated | 4/6 | 0 | 2 | XAG_USD | 1.436 |
| Cointegration / Z-score MR | ✅ Validated | 2/6 | 0 | 4 | NAS100_USD | 1.007 |
| ATR-Scaled Triple EMA | ⚠️ Marginal | 1/6 | 0 | 5 | NAS100_USD | 0.560 |

### General Tab Strategy Details
- **RSI(2) Connors** — `strategy_rsi2_connors.py` — ✅ 5/6 pass (XAU 0.590, NAS100 0.583, BTC 0.489, USD_TRY 0.442, BCO 0.363 — XAG failed)
  Params: SMA(200) trend filter, RSI(2)<5 long / RSI(2)>95 short, exit at RSI>65 or SMA(5) crossover
- **Kalman MR v3** — `strategy_kalman_mean_reversion.py` — ✅ 4/6 pass (XAG 1.436, BTC 1.359, USD_TRY 3.438, BCO 0.650 — XAU and NAS100 failed)
  Params: ATR-stop (mult=1.5), min_hold=8 bars, max_hold=30 bars. Fixed: replaced crossover exit with ATR-stop to prevent always-in-market.
- **Cointegration / Z-score MR** — `strategy_cointegration_pairs.py` — ✅ 2/6 pass (NAS100 1.007, BTC 0.721 — all others failed)
  Params: lookback=20, entry=2.0σ, exit at mean. Fixed: reduced lookback from 100→20 for H4 compatibility.
- **ATR-Scaled Triple EMA** — `strategy_atr_scaled_mean_reversion.py` — ⚠️ Marginal: NAS100 only (0.560 Sharpe)
  Params: EMA(10/50/200) triple filter + ATR bands. Issue: only 3–7 trades in 400 days. EMA(200) too slow for H4.

## Methodology
- **IS period**: 2015-01-01 to 2019-12-31
- **OOS period**: 2020-01-01 to 2025-01-01
- **Entry**: OPEN price (not close)
- **Stops**: Intra-candle H/L checking
- **Position sizing**: Kelly two-pass (collect trades at base risk → compute Kelly → re-scale)
- **Kelly bounds**: min 0.08%, max 1.0%
- **Spread costs**: Per-instrument (BTC 0.10%, XAU 0.05%, BCO 0.12%, USD_TRY 0.08%, NAS100 0.04%, XAG 0.08%)
- **Starting capital**: $10,000
- **Status criteria**: Sharpe > 0.3 AND DD > -25% = PASS
