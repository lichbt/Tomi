#!/bin/bash
# Daily backup script for OpenClaw/Tomi agent setup
# Runs at 4:30am daily

set -e  # Exit on error

# Configuration
BACKUP_DIR="/tmp/openclaw_backup_$(date +%Y%m%d_%H%M%S)"
REPO_DIR="/tmp/tomi_backup_repo"
GIT_REPO="git@github.com-Tomi-deploy:lichbt/Tomi.git"
LOG_FILE="/tmp/openclaw_backup_$(date +%Y%m%d).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

error() {
    log "${RED}ERROR: $1${NC}"
    exit 1
}

success() {
    log "${GREEN}SUCCESS: $1${NC}"
}

warning() {
    log "${YELLOW}WARNING: $1${NC}"
}

# Function to send Telegram notification
send_telegram() {
    local message="$1"
    local bot_token="8744307274:AAHTK9b7-eaHI8gbkAh90xDa64zFaUdlEpM"
    local chat_id="5719279617"  # Your Telegram user ID
    
    # URL encode the message
    local encoded_message=$(echo "$message" | sed 's/ /%20/g; s/\n/%0A/g')
    
    # Send via curl
    curl -s -X POST "https://api.telegram.org/bot$bot_token/sendMessage" \
        -d "chat_id=$chat_id" \
        -d "text=$encoded_message" \
        -d "disable_notification=false" > /dev/null 2>&1
}

# Start backup
log "Starting OpenClaw agent backup..."

# Create backup directory
mkdir -p "$BACKUP_DIR"
log "Created backup directory: $BACKUP_DIR"

# Function to sanitize secrets in a file
sanitize_file() {
    local src_file="$1"
    local dest_file="$2"
    
    if [ ! -f "$src_file" ]; then
        warning "File not found: $src_file"
        return 1
    fi
    
    # Create a copy
    cp "$src_file" "$dest_file"
    
    # Common secret patterns to sanitize
    # API keys, tokens, passwords, etc.
    
    # OpenAI/Claude API keys
    sed -i '' -E 's/(sk-(proj-)?[a-zA-Z0-9]{48})/[OPENAI_API_KEY]/g' "$dest_file"
    sed -i '' -E 's/(sk-ant-[a-zA-Z0-9]{48})/[ANTHROPIC_API_KEY]/g' "$dest_file"
    
    # Generic API keys (32-64 char alphanumeric)
    sed -i '' -E 's/([a-zA-Z0-9]{32,64})/[GENERIC_API_KEY]/g' "$dest_file"
    
    # Bot tokens (Telegram: numbers:letters pattern)
    sed -i '' -E 's/([0-9]{8,10}:[a-zA-Z0-9_-]{35})/[TELEGRAM_BOT_TOKEN]/g' "$dest_file"
    
    # GitHub tokens
    sed -i '' -E 's/(gh[pors]_[a-zA-Z0-9]{36})/[GITHUB_TOKEN]/g' "$dest_file"
    
    # AWS keys
    sed -i '' -E 's/(AKIA[0-9A-Z]{16})/[AWS_ACCESS_KEY]/g' "$dest_file"
    sed -i '' -E 's/([a-zA-Z0-9+/]{40})/[AWS_SECRET_KEY]/g' "$dest_file"
    
    # Database URLs with passwords
    sed -i '' -E 's/(mongodb|postgresql|mysql):\/\/[^:]+:[^@]+@/[DB_TYPE]:\/\/[USER]:[PASSWORD]@/g' "$dest_file"
    
    # Email passwords
    sed -i '' -E 's/("password":\s*")[^"]+"/"password": "[EMAIL_PASSWORD]"/g' "$dest_file"
    
    log "Sanitized: $src_file -> $dest_file"
}

# Backup critical directories
log "Backing up critical files..."

# 1. Workspace files
mkdir -p "$BACKUP_DIR/workspace"
cp -r /Users/lich/.openclaw/workspace/* "$BACKUP_DIR/workspace/" 2>/dev/null || warning "Some workspace files not copied"

# 2. OpenClaw config
mkdir -p "$BACKUP_DIR/config"
sanitize_file "/Users/lich/.openclaw/openclaw.json" "$BACKUP_DIR/config/openclaw.json"

# 3. Memory files
mkdir -p "$BACKUP_DIR/memory"
cp -r /Users/lich/.openclaw/workspace/memory/* "$BACKUP_DIR/memory/" 2>/dev/null || warning "No memory files found"

# 4. Check for cron jobs
log "Checking for cron jobs..."
crontab -l > "$BACKUP_DIR/crontab.txt" 2>/dev/null || warning "No crontab found or cannot access"

# 5. Check for skills directory
if [ -d "/opt/homebrew/lib/node_modules/openclaw/skills" ]; then
    mkdir -p "$BACKUP_DIR/skills"
    find /opt/homebrew/lib/node_modules/openclaw/skills -name "SKILL.md" -exec cp {} "$BACKUP_DIR/skills/" \; 2>/dev/null || warning "Some skill files not copied"
fi

# 6. Environment and shell config
log "Backing up environment config..."
printenv | sort > "$BACKUP_DIR/environment.txt" 2>/dev/null || warning "Could not capture environment"
[ -f ~/.zshrc ] && cp ~/.zshrc "$BACKUP_DIR/" 2>/dev/null || warning "No .zshrc found"
[ -f ~/.bashrc ] && cp ~/.bashrc "$BACKUP_DIR/" 2>/dev/null || warning "No .bashrc found"
[ -f ~/.bash_profile ] && cp ~/.bash_profile "$BACKUP_DIR/" 2>/dev/null || warning "No .bash_profile found"

# Create manifest
log "Creating backup manifest..."
{
    echo "OpenClaw Backup Manifest - $(date)"
    echo "======================================"
    echo "Backup created: $(date)"
    echo "Backup directory: $BACKUP_DIR"
    echo ""
    echo "Files included:"
    find "$BACKUP_DIR" -type f | sort
    echo ""
    echo "Total files: $(find "$BACKUP_DIR" -type f | wc -l)"
    echo "Total size: $(du -sh "$BACKUP_DIR" | cut -f1)"
} > "$BACKUP_DIR/MANIFEST.md"

# Load SSH key for GitHub
log "Setting up SSH for GitHub..."
eval "$(ssh-agent -s)" > /dev/null 2>&1
ssh-add ~/.ssh/id_ed25519_Tomi_deploy > /dev/null 2>&1 || warning "Could not load SSH key"

# Test SSH connection
ssh -o "StrictHostKeyChecking=no" -T git@github.com-Tomi-deploy 2>&1 | grep -i "successfully\|authenticated" > /dev/null || warning "SSH connection test failed"

# Git operations
log "Setting up git repository..."

if [ ! -d "$REPO_DIR" ]; then
    git clone "$GIT_REPO" "$REPO_DIR" || error "Failed to clone repository"
else
    cd "$REPO_DIR"
    git pull origin main || warning "Failed to pull latest changes"
fi

# Clear existing repo and copy new backup
cd "$REPO_DIR"
rm -rf ./*
cp -r "$BACKUP_DIR"/* .

# Commit and push
log "Committing changes..."
git add .
git commit -m "OpenClaw backup $(date '+%Y-%m-%d %H:%M')

- Automated daily backup
- Workspace: $(find "$BACKUP_DIR/workspace" -type f 2>/dev/null | wc -l) files
- Memory: $(find "$BACKUP_DIR/memory" -type f 2>/dev/null | wc -l) files
- Config: openclaw.json (sanitized)
- Skills: $(find "$BACKUP_DIR/skills" -type f 2>/dev/null | wc -l) SKILL.md files
- Environment and cron included"

log "Pushing to GitHub..."
git push origin main || error "Failed to push to GitHub"

# Cleanup
log "Cleaning up..."
rm -rf "$BACKUP_DIR"

success "Backup completed and pushed to GitHub repository"
log "Backup log saved to: $LOG_FILE"

# Send Telegram notification
log "Sending Telegram notification..."
if send_telegram "✅ OpenClaw backup completed $(date '+%Y-%m-%d %H:%M'). Files pushed to GitHub."; then
    log "Telegram notification sent successfully"
else
    warning "Failed to send Telegram notification"
fi

log "Backup script finished successfully"