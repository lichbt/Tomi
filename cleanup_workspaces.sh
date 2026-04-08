#!/bin/bash
# cleanup_workspaces.sh — Remove old backups, fix symlinks
set -e

OPENCLAW="/Users/lich/.openclaw"
WORKSPACE="$OPENCLAW/workspace"
SHARED="$WORKSPACE/shared"

echo "🧹 WORKSPACE CLEANUP"
echo "===================="
echo ""

# =============================================================================
# 1. Remove old backup files and orphaned folders
# =============================================================================
echo "📦 Removing old backups and orphaned folders..."

# workspace (main)
rm -rf "$WORKSPACE/strategies.local_"* 2>/dev/null && echo "  ✅ workspace: removed strategies.local_*"
rm -f "$WORKSPACE/research_log.md.bak_"* && echo "  ✅ workspace: removed research_log.md.bak_*"
rm -rf "$WORKSPACE/backtester" 2>/dev/null && echo "  ✅ workspace: removed backtester/ (now in shared/)"
rm -rf "$WORKSPACE/trading" 2>/dev/null && echo "  ✅ workspace: removed trading/"

# workspace-coder
rm -rf "$WORKSPACE/../workspace-coder/strategies.local_"* 2>/dev/null && echo "  ✅ workspace-coder: removed strategies.local_*"
rm -f "$WORKSPACE/../workspace-coder/research_log.md.bak_"* && echo "  ✅ workspace-coder: removed research_log.md.bak_*"
rm -f "$WORKSPACE/../workspace-coder/alloc_engine_bak.py" && echo "  ✅ workspace-coder: removed alloc_engine_bak.py"
rm -f "$WORKSPACE/../workspace-coder/alloc_engine_v11.py" && echo "  ✅ workspace-coder: removed alloc_engine_v11.py"
rm -f "$WORKSPACE/../workspace-coder/alloc_engine_v12.py" && echo "  ✅ workspace-coder: removed alloc_engine_v12.py"
rm -f "$WORKSPACE/../workspace-coder/alloc_engine.py.bak" && echo "  ✅ workspace-coder: removed alloc_engine.py.bak"
rm -f "$WORKSPACE/../workspace-coder/backtest_results.txt" && echo "  ✅ workspace-coder: removed backtest_results.txt (961KB)"

# workspace-allocator
rm -f "$WORKSPACE/../workspace-allocator/alloc_engine.py.bak" && echo "  ✅ workspace-allocator: removed alloc_engine.py.bak"
rm -f "$WORKSPACE/../workspace-allocator/alloc_engine_v11.py" && echo "  ✅ workspace-allocator: removed alloc_engine_v11.py"
rm -f "$WORKSPACE/../workspace-allocator/alloc_engine_v12.py.new" && echo "  ✅ workspace-allocator: removed alloc_engine_v12.py.new"

echo ""

# =============================================================================
# 2. Fix missing symlinks in workspace-backtester
# =============================================================================
echo "🔗 Setting up symlinks for workspace-backtester..."
WS_BT="$OPENCLAW/workspace-backtester"

# Backup and remove old folders before symlinking
[[ -d "$WS_BT/strategies" ]] && mv "$WS_BT/strategies" "$WS_BT/strategies.bak_$(date +%s)" 2>/dev/null || true
[[ -d "$WS_BT/data" ]] && mv "$WS_BT/data" "$WS_BT/data.bak_$(date +%s)" 2>/dev/null || true
[[ -f "$WS_BT/research_log.md" ]] && mv "$WS_BT/research_log.md" "$WS_BT/research_log.md.bak_$(date +%s)" 2>/dev/null || true

ln -sf "$SHARED/strategies" "$WS_BT/strategies"
ln -sf "$SHARED/research/research_log.md" "$WS_BT/research_log.md"
echo "  ✅ workspace-backtester: symlinks created"

# =============================================================================
# 3. Fix missing symlinks in workspace-executioner
# =============================================================================
echo "🔗 Setting up symlinks for workspace-executioner..."
WS_EX="$OPENCLAW/workspace-executioner"

[[ -f "$WS_EX/research_log.md" ]] && mv "$WS_EX/research_log.md" "$WS_EX/research_log.md.bak_$(date +%s)" 2>/dev/null || true

ln -sf "$SHARED/research/research_log.md" "$WS_EX/research_log.md"
echo "  ✅ workspace-executioner: symlinks created"

# =============================================================================
# 4. Fix missing symlinks in workspace-groot
# =============================================================================
echo "🔗 Setting up symlinks for workspace-groot..."
WS_GR="$OPENCLAW/workspace-groot"

[[ -f "$WS_GR/research_log.md" ]] && mv "$WS_GR/research_log.md" "$WS_GR/research_log.md.bak_$(date +%s)" 2>/dev/null || true

ln -sf "$SHARED/research/research_log.md" "$WS_GR/research_log.md"
echo "  ✅ workspace-groot: symlinks created"

# =============================================================================
# 5. Verify all symlinks
# =============================================================================
echo ""
echo "🔍 VERIFYING SYMLINKS"
echo "====================="

WORKSPACES="workspace workspace-coder workspace-backtester workspace-alpha-hunter workspace-allocator workspace-executioner workspace-groot"

for ws in $WORKSPACES; do
    WS_DIR="$OPENCLAW/$ws"
    [[ -d "$WS_DIR" ]] || continue
    
    echo ""
    echo "--- $ws ---"
    
    # Check research_log.md
    if [[ -L "$WS_DIR/research_log.md" ]]; then
        TARGET=$(readlink "$WS_DIR/research_log.md")
        echo "  ✅ research_log.md → $TARGET"
    elif [[ -f "$WS_DIR/research_log.md" ]]; then
        echo "  ⚠️  research_log.md is a FILE (not symlink)"
    else
        echo "  ❌ research_log.md MISSING"
    fi
    
    # Check strategies (except executioner/groot which don't need it)
    if [[ -d "$WS_DIR" ]] && [[ "$ws" != "workspace-executioner" ]] && [[ "$ws" != "workspace-groot" ]]; then
        if [[ -L "$WS_DIR/strategies" ]]; then
            TARGET=$(readlink "$WS_DIR/strategies")
            echo "  ✅ strategies/ → $TARGET"
        elif [[ -d "$WS_DIR/strategies" ]]; then
            echo "  ⚠️  strategies/ is a FOLDER (not symlink)"
        else
            echo "  ⚠️  strategies/ MISSING (or not needed for this agent)"
        fi
    fi
done

echo ""
echo "✅ CLEANUP COMPLETE"
echo ""
echo "Next: Commit changes with 'git add -A && git commit -m \"Cleanup workspaces\"'"
