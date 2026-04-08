# SHARED Memory — Cross-Agent Institutional Knowledge

> All agents contribute to this memory. This is what "institutional knowledge" looks like.

## Key Learnings

### What Works
- Kelly weighting over uniform risk allocation (Sharpe improvement: 1.546 → 2.032)
- Daily timeframe consistently outperforms H4 across strategies
- Mean reversion fails on H4 due to costs; only trend-following survives
- Portfolio naturally diversifies: avg 2.25 concurrent positions

### What Doesn't Work
- Overly complex strategies with >4 indicators (overfitting)
- Pure mean reversion without trend filter on H4
- Insufficient sample size (<50 trades) for validation

### Strategy Categories That Work
1. Trend-following on Daily timeframe
2. Volatility expansion on H4
3. Regime-based switching (HMM/ADX)
4. Supertrend variants with volume confirmation

## Validated Strategies (Production Ready)
## Key Decisions
- **Kelly weighting** over uniform risk allocation (Sharpe improvement: 1.546 → 2.032)
- **Risk-per-trade** sizing preferred for small account compounding
- **Daily timeframe** consistently outperforms H4 across strategies
- **Mean reversion** fails on H4 due to costs; only trend-following survives
- **Portfolio naturally diversifies:** avg 2.25 concurrent positions, <0.3% chance of 6 concurrent

## Current State (2026-04-06)
- **Executioner:** Functional, Oanda connection OK, deployed BCO and XAU positions live per user update
- **Allocator:** Manages Kelly weights and portfolio composition
- **Backtester:** Comprehensive backtest framework with Oanda real data
- **Coder:** Strategy development and validation pipeline mature
- **Alpha-hunter:** Agent template created, needs system prompt configuration
- **Backup:** Daily cron job at 4:30am configured and running

## Live Positions (User Update 16:11-16:12 GMT+7)
- **BCO_USD** - Volatility Expansion strategy (H4)
- **XAU_USD** - MACD Momentum strategy (Daily)
- **Executioner confirmed working** - live deployment successful post-weekend

## Open Tasks
- Monitor live positions via executioner logs
- Wait for Coder Agent to code Choppiness Index Mean Reversion strategy
- Verify cron job execution and outputs
- Ensure backup push to GitHub works correctly
- Consider deploying additional strategies from the 6-strategy portfolio

## 2026-04-06 - Daily Summary
- Fixed 6 failing cron jobs (rate limit errors) - removed and recreated with proper scheduling
- Verified executioner agent functionality from April 4 log (weekend deployment failure expected)
- Confirmed BCO and XAU positions are live per user 16:11 GMT+7 update
- Delegated Choppiness Index Mean Reversion strategy coding to Coder Agent (prototype file removed per orchestrator role)
- All cron jobs now idle and scheduled: portfolio check every 4h, midnight pipeline, daily backup (4:30am), morning report (6:30am), daily portfolio report (8:00am), weekly report (Mondays 9:00am), memory dreaming (3:00am)
