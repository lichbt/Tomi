#!/bin/bash
# ═══════════════════════════════════════════════════════════
# STRATEGY PIPELINE — 6-Stage Orchestration
# Usage: ./pipeline.sh "research new strategies"
# ═══════════════════════════════════════════════════════════
set -e

PIPELINE_LOG="/Users/lich/.openclaw/shared/pipeline_log.md"
RESEARCH_LOG="/Users/lich/.openclaw/shared/research_log.md"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$PIPELINE_LOG"
}

# ── Stage 1: Research ───────────────────────────────
STAGE_RESEARCH() {
    log "📈 STAGE 1/6 — Researching new strategies..."
    openclaw agent --agent alpha-hunter \
        --message "You are the Researcher. Search the web for new trading strategies we haven't tested yet. We already have: Donchian, Volatility, RSI, MACD, Multi-Timeframe, Pivot Points, Ichimoku, Stochastic, Keltner. Write findings to $RESEARCH_LOG with strategy name, source URL, core logic, expected edge, and Python pseudocode. Find at least 5 new strategies." \
        --timeout 600
    log "✅ Stage 1 complete — research written to $RESEARCH_LOG"
}

# ── Stage 2: Code ───────────────────────────────────
STAGE_CODE() {
    log "⚙️  STAGE 2/6 — Coding strategies..."
    0
STAGE4
        --message "Read the latest research_log.md and implement each new strategy as strategies/strategy_<name>.py. Use vectorized pandas/numpy only. Include ATR trailing stops, .shift(1) to prevent look-ahead bias, and proper type hints. Save to /Users/lich/.openclaw/workspace-coder/strategies/" \
        --timeout 600
    log "✅ Stage 2 complete — strategies coded"
}

# ── Stage 3: Backtest ───────────────────────────────
STAGE_BACKTEST() {
    log "🧪 STAGE 3/6 — Running backtests..."
    openclaw agent --agent backtester \
        --message "Backtest all new strategies from /Users/lich/.openclaw/workspace-coder/strategies/ across all Oanda instruments on H4 and Daily. IS: 2015-2019, OOS: 2020-2025 (H4) / 2020-2026 (D). Report: OOS Sharpe, OOS/IS ratio, annual return, max DD. Viable = OOS Sharpe > 0.3 AND OOS/IS > 0.4. Use data/fetcher.py get_real_data() with Parquet cache." \
        --timeout 1800
    log "✅ Stage 3 complete — backtests done"
}

# ── Stage 4: Monte Carlo ────────────────────────────
STAGE_MC() {
    log "📊 STAGE 4/6 — Running Monte Carlo simulations..."
    openclaw agent --agent backtester \
        --message "Run Monte Carlo (10,000 sims) on the backtest results. Keep only strategies with Ruin Risk < 5%, Worst 5% DD < 30%. Report final viable list." \
        --timeout 1800
    log "✅ Stage 4 complete — MC done"
}

# ── Stage 5: Allocate ───────────────────────────────
STAGE_ALLOCATE() {
    log "⚖️  STAGE 5/6 — Optimizing portfolio allocation..."
    0
STAGE4
        --message "Take the viable strategies from the backtest/MC results and update the portfolio allocation in /Users/lich/.openclaw/workspace-allocator/alloc_engine.py. Run the allocator to generate the final portfolio with Sharpe-optimized, correlation-capped weights. Report final portfolio and constraint checks." \
        --timeout 600
    log "✅ Stage 5 complete — allocation optimized"
}

# ── Stage 6: Deploy ─────────────────────────────────
STAGE_DEPLOY() {
    log "⚔️  STAGE 6/6 — Deploying to Oanda..."
    0
STAGE4
        --message "Execute the final portfolio allocation via the Executioner engine at /Users/lich/.openclaw/workspace-executioner/execution_engine.py. Run preflight check, then execute orders for any new positions. Report: filled orders, rejects, latency, slippage." \
        --timeout 600
    log "✅ Stage 6 complete — deployed"
}

# ── Main ────────────────────────────────────────────
log "═══════════════════════════════════════════════"
log "🚀 STRATEGY PIPELINE START"
log "═══════════════════════════════════════════════"

# Run all stages
STAGE_RESEARCH
STAGE_CODE
STAGE_BACKTEST
STAGE_MC
STAGE_ALLOCATE

# Ask before deploying (destructive)
echo ""
log "⚠️  Stages 1-5 complete. Ready to deploy. Type 'yes' to execute STAGE 6:"
read -r confirm
if [ "$confirm" = "yes" ]; then
    STAGE_DEPLOY
else
    log "⏸️  Deployment skipped. Pipeline ready for manual review."
fi

log "═══════════════════════════════════════════════"
log "🏁 PIPELINE COMPLETE"
log "═══════════════════════════════════════════════"
