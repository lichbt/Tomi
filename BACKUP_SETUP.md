# OpenClaw Backup System Setup

## Overview
This system automatically backs up your OpenClaw configuration daily at 4:30am to a private GitHub repository (`lichbt/Tomi`).

## What Gets Backed Up
- ✅ Workspace files (`/Users/lich/.openclaw/workspace/`)
- ✅ Memory files (`memory/` directory)
- ✅ Configuration (`openclaw.json` with secrets sanitized)
- ✅ Skill definitions (`SKILL.md` files)
- ✅ Cron job definitions
- ✅ Environment configuration
- ✅ Shell profiles (`.zshrc`, `.bashrc`, etc.)

## Secret Protection
All files are scanned for secrets (API keys, tokens, passwords) before backup. Secrets are replaced with placeholders like `[OPENAI_API_KEY]` to keep your credentials safe.

## Setup Instructions

### 1. First-Time Setup
Run the master setup script:
```bash
chmod +x /Users/lich/.openclaw/workspace/setup_backup_system.sh
/Users/lich/.openclaw/workspace/setup_backup_system.sh
```

### 2. Add Deploy Key to GitHub
The setup script will show you a public key. Add it to your GitHub repository:
1. Go to: `https://github.com/lichbt/Tomi/settings/keys`
2. Click "Add deploy key"
3. Title: "OpenClaw Backup Deploy Key"
4. Paste the public key
5. ✅ Check "Allow write access"
6. Click "Add key"

### 3. Test the System
Run a manual backup test:
```bash
/Users/lich/.openclaw/workspace/backup_agent_setup.sh
```

## Files Created
- `~/.ssh/id_ed25519_Tomi_deploy` - SSH private key (keep this secure!)
- `~/.ssh/id_ed25519_Tomi_deploy.pub` - SSH public key (add to GitHub)
- `~/.ssh/config` - SSH configuration for deploy key
- Various scripts in `/Users/lich/.openclaw/workspace/`

## Scripts
- `backup_agent_setup.sh` - Main backup script (runs at 4:30am)
- `secret_scanner.py` - Secret detection and sanitization
- `setup_deploy_key.sh` - GitHub deploy key setup
- `setup_cron_job.sh` - Cron job setup
- `setup_backup_system.sh` - Complete setup wizard
- `test_backup.sh` - Test script

## Manual Operations

### Run Backup Manually
```bash
/Users/lich/.openclaw/workspace/backup_agent_setup.sh
```

### Check Cron Job
```bash
crontab -l
```

### View Backup Logs
```bash
# Today's log
tail -f /tmp/openclaw_backup_$(date +%Y%m%d).log

# Cron job log
tail -f /tmp/openclaw_backup_cron.log
```

### Remove Cron Job
```bash
crontab -e
# Delete the line with "backup_agent_setup.sh"
```

## Telegram Notifications
You'll receive a Telegram message after each backup:
- ✅ Success: "OpenClaw backup completed [timestamp]. Files pushed to GitHub."
- ❌ Failure: Error details in log files

## Troubleshooting

### SSH Connection Fails
```bash
# Test SSH connection
ssh -T git@github.com-Tomi-deploy

# Check SSH key
ls -la ~/.ssh/id_ed25519_Tomi_deploy*

# Verify GitHub deploy key has write access
```

### Backup Fails
Check logs:
```bash
cat /tmp/openclaw_backup_$(date +%Y%m%d).log
cat /tmp/openclaw_backup_cron.log
```

### Cron Job Not Running
```bash
# Check cron service
sudo systemctl status cron  # On Linux
# or
sudo launchctl list | grep cron  # On macOS

# Check your user's crontab
crontab -l
```

## Security Notes
- Deploy keys are repository-specific (safer than personal SSH keys)
- Secrets are sanitized before backup
- Private key stays on your machine only
- Backups go to your private GitHub repository

## Maintenance
The system requires no maintenance. It will:
- Run daily at 4:30am
- Sanitize secrets automatically
- Push changes to GitHub
- Send Telegram notifications
- Log all activity

## Need Help?
Check the logs first. If issues persist, the backup scripts are in `/Users/lich/.openclaw/workspace/`.