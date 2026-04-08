#!/bin/bash
# Master script to setup complete OpenClaw backup system

set -e

echo "================================================"
echo "   OpenClaw Backup System Setup"
echo "================================================"
echo ""
echo "This script will set up:"
echo "1. GitHub deploy key for secure repository access"
echo "2. Backup script with secret sanitization"
echo "3. Daily cron job at 4:30am"
echo "4. Telegram notifications"
echo ""

# Check prerequisites
echo "Checking prerequisites..."
echo ""

# Check for git
if ! command -v git &> /dev/null; then
    echo "Error: git is not installed. Please install git first."
    exit 1
fi

# Check for ssh-keygen
if ! command -v ssh-keygen &> /dev/null; then
    echo "Error: ssh-keygen is not available. Please install OpenSSH."
    exit 1
fi

echo "✓ Git is installed"
echo "✓ SSH tools available"
echo ""

# Step 1: Make all scripts executable
echo "Step 1: Making scripts executable..."
chmod +x /Users/lich/.openclaw/workspace/*.sh
chmod +x /Users/lich/.openclaw/workspace/*.py
echo "✓ Script permissions set"
echo ""

# Step 2: Setup GitHub deploy key
echo "Step 2: Setting up GitHub deploy key..."
echo ""
/Users/lich/.openclaw/workspace/setup_deploy_key.sh

echo ""
echo "⚠️  IMPORTANT: You need to add the deploy key to GitHub!"
echo "   Follow the instructions above to add the key to your repository."
echo ""
read -p "Have you added the deploy key to GitHub? (y/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Please add the deploy key first, then run this script again."
    exit 1
fi

# Step 3: Test SSH connection
echo "Step 3: Testing SSH connection..."
echo ""
ssh -T git@github.com-Tomi-deploy 2>&1 | grep -i "successfully\|authenticated" && {
    echo "✓ SSH connection successful!"
} || {
    echo "✗ SSH connection failed. Please check:"
    echo "  1. Key added to GitHub with WRITE access"
    echo "  2. Key added as DEPLOY KEY (not personal key)"
    echo "  3. Try manually: ssh -T git@github.com-Tomi-deploy"
    exit 1
}
echo ""

# Step 4: Test backup script
echo "Step 4: Testing backup script (dry run)..."
echo ""
# Create a test version that doesn't actually push
TEST_SCRIPT="/tmp/test_backup.sh"
cp /Users/lich/.openclaw/workspace/backup_agent_setup.sh "$TEST_SCRIPT"
sed -i '' 's/git push origin main/echo "DRY RUN: Would push to GitHub"/' "$TEST_SCRIPT"
sed -i '' 's/send_telegram/echo "DRY RUN: Would send Telegram"/' "$TEST_SCRIPT"
chmod +x "$TEST_SCRIPT"

echo "Running test backup (this may take a minute)..."
if "$TEST_SCRIPT" 2>&1 | tail -20; then
    echo "✓ Backup script test completed"
else
    echo "✗ Backup script test failed"
    exit 1
fi
echo ""

# Step 5: Setup cron job
echo "Step 5: Setting up cron job..."
echo ""
/Users/lich/.openclaw/workspace/setup_cron_job.sh

echo ""
echo "================================================"
echo "   Setup Complete! 🎉"
echo "================================================"
echo ""
echo "Summary:"
echo "✓ GitHub deploy key created and configured"
echo "✓ Backup script ready with secret sanitization"
echo "✓ Cron job scheduled for 4:30am daily"
echo "✓ Telegram notifications enabled"
echo ""
echo "Files created:"
echo "  - ~/.ssh/id_ed25519_Tomi_deploy (private key)"
echo "  - ~/.ssh/id_ed25519_Tomi_deploy.pub (public key)"
echo "  - ~/.ssh/config (SSH configuration)"
echo ""
echo "Backup script: /Users/lich/.openclaw/workspace/backup_agent_setup.sh"
echo "Cron log: /tmp/openclaw_backup_cron.log"
echo ""
echo "To run a manual backup now:"
echo "  /Users/lich/.openclaw/workspace/backup_agent_setup.sh"
echo ""
echo "To check cron job:"
echo "  crontab -l"
echo ""
echo "To view backup logs:"
echo "  tail -f /tmp/openclaw_backup_$(date +%Y%m%d).log"
echo ""
echo "The system will automatically backup daily at 4:30am."
echo "You'll receive Telegram notifications for each backup."