# SHARED/ — Unified Workspace for All Agents

This directory is the **single source of truth** for all agents.

## Structure
```
SHARED/
├── research/           # Research logs (ONE research_log.md)
├── strategies/         # All strategy code
├── backtests/         # All backtest results
├── memory/            # Shared memory and learnings
└── agents/           # Agent-specific shared configs
```

## How It Works
- Each workspace has its own SOUL.md/IDENTITY.md for context isolation
- But ALL workspaces symlink to these shared files for coordination
- No more "coder doesn't know what backtester is doing"
