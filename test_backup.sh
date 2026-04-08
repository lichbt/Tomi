#!/bin/bash
# Test backup script

echo "Testing backup setup..."
echo "Current directory: $(pwd)"
echo "User: $(whoami)"
echo "Date: $(date)"

# Test SSH access to GitHub
echo -e "\nTesting SSH access to GitHub..."
ssh -T git@github.com 2>&1 | head -5

# List critical files
echo -e "\nCritical OpenClaw files:"
ls -la /Users/lich/.openclaw/ 2>/dev/null || echo "OpenClaw directory not found"
echo ""
ls -la /Users/lich/.openclaw/workspace/ 2>/dev/null || echo "Workspace not found"

# Check if git is configured
echo -e "\nGit configuration:"
git config --global --list 2>/dev/null | head -10 || echo "No git config found"

echo -e "\nTest complete."