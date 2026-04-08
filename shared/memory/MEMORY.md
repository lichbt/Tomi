# ❄️ COLD Memory — Long-Term Archive

> Historical decisions, milestones, distilled lessons. Updated during archival phases.

---

## 🏆 Key Achievements (2026)

### Pipeline Established
- Full strategy pipeline: Research → Code → Backtest → Validate → Deploy
- 44 strategies in shared/strategies/
- Kelly-weighted portfolio v13 deployed
- Live positions: BCO_USD, XAU_USD

### Architecture Evolution
- **2026-04-08:** Unified workspace/ with shared/ folder
  - All agents now symlink to shared/ for work files
  - Removed alpha-hunter and coder crons (now manual trigger)
  - All cron jobs use free models

---

## 📊 Strategy Performance Learnings

### What Works ✅
| Strategy | Timeframe | Instruments | Sharpe | Notes |
|----------|-----------|-------------|--------|-------|
| Elder's Impulse | Daily | XAU_USD | 1.545 | Best performer |
| Choppiness Index MR | Daily | NAS100_USD | 0.914 | |
| Elder's Impulse | Daily | XAG_USD | 0.619 | |
| FRAMA | H4 | EURUSD | Mixed | Currently backtesting |

### What Failed ❌
- Pure mean reversion on H4 (costs eat profits)
- Strategies with >4 indicators (overfitting)
- Strategies with <50 trades (insufficient sample)
- BTC_USD Elder Impulse (Sharpe -0.99, DD -48.5%)

### Portfolio Insights
- Kelly weighting: Sharpe 1.546 → 2.032 (+31%)
- Average 2.25 concurrent positions
- Daily timeframe outperforms H4
- Mean reversion only works with trend filter

---

## 🎓 Distilled Wisdom

### On Strategy Design
1. Every strategy needs a trend filter (EMA, ADX, etc.)
2. Every strategy needs a momentum confirmation
3. Max 4 indicators to avoid overfitting
4. Use .shift(1) to avoid lookahead bias

### On Backtesting
1. IS/OOS ratio < 0.4 = overfitted
2. MC ruin > 5% = reject
3. Sharpe < 1.5 + p-value > 0.05 = reject
4. < 50 trades = insufficient sample

### On Portfolio
1. Kelly weighting > uniform risk
2. Correlations < 0.7 between positions
3. Max 30% in any sector
4. Rebalance when positions drift > 20%

---

## 📅 Major Decision Log

| Date | Decision | Outcome |
|------|----------|---------|
| 2026-04-01 | Deploy Kelly-weighted portfolio v13 | Live, working |
| 2026-04-06 | Remove failing cron jobs, consolidate to free models | Done |
| 2026-04-08 | Create unified workspace/shared/ architecture | Done |
| 2026-04-08 | Remove alpha-hunter/coder crons | Done |
| 2026-04-08 | Set up memory tiering (HOT/WARM/COLD) | Done |

---

## 🔮 Active Projects

- Monitoring live positions (BCO_USD, XAU_USD)
- Pending: Telegram bot re-add to group
- Pending: Test new HEARTBEAT schedule (8AM/12PM/6PM)
- Pending: First weekly memory distillation (Sunday)

---

*Last updated: 2026-04-08*
