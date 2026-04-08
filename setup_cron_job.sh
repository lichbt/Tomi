#!/bin/bash
# Setup cron job for daily OpenClaw backup at 4:30am

set -e

echo "Setting up cron job for OpenClaw backup..."
echo ""

BACKUP_SCRIPT="/Users/lich/.openclaw/workspace/backup_agent_setup.sh"
CRON_JOB="30 4 * * * /bin/bash $BACKUP_SCRIPT >> /tmp/openclaw_backup_cron.log 2>&1"

# Check if backup script exists
if [ ! -f "$BACKUP_SCRIPT" ]; then
    echo "Error: Backup script not found at $BACKUP_SCRIPT"
    exit 1
fi

# Make sure backup script is executable
chmod +x "$BACKUP_SCRIPT"
echo "Backup script permissions updated."

# Check current crontab
echo ""
echo "Current crontab:"
crontab -l 2>/dev/null || echo "(No crontab found)"

echo ""
echo "Proposed cron job:"
echo "$CRON_JOB"
echo ""

# Ask for confirmation
read -p "Add this cron job? (y/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Add cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo ""
echo "Cron job added successfully!"
echo ""

# Verify
echo "Updated crontab:"
crontab -l

echo ""
echo "Cron job details:"
echo "- Runs daily at 4:30am"
echo "- Executes: $BACKUP_SCRIPT"
echo "- Logs to: /tmp/openclaw_backup_cron.log"
echo "- Errors also logged to same file"
echo ""

# Test instructions
echo "To test the backup manually:"
echo "  $BACKUP_SCRIPT"
echo ""
echo "To check cron logs:"
echo "  tail -f /tmp/openclaw_backup_cron.log"
echo ""
echo "To remove the cron job later:"
echo "  crontab -e"
echo "  (Then delete the line with 'backup_agent_setup.sh')"
echo ""
echo "Setup complete! The backup will run automatically at 4:30am daily."