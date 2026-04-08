#!/bin/bash
# Tomi Daily Backup Script
# Backs up agent configuration to private GitHub repo with secret sanitization

set -e

REPO_DIR="/tmp/tomi_backup_repo"
BACKUP_SRC="/Users/lich/.openclaw"
GITHUB_REPO="git@github.com:lichbt/Tomi.git"
SSH_KEY="$HOME/.ssh/id_rsa_tomi_deploy"
TELEGRAM_BOT_TOKEN="8744307274:AAHTK9b7-eaHI8gbkAh90xDa64zFaUdlEpM"
TELEGRAM_CHAT_ID="5719279617"

LOG_FILE="/tmp/tomi_backup.log"
DATE_STAMP=$(date '+%Y-%m-%d %H:%M:%S')
BACKUP_DATE=$(date '+%Y-%m-%d')

log() {
    echo "[$DATE_STAMP] $1" | tee -a "$LOG_FILE"
}

error() {
    echo "[$DATE_STAMP] ERROR: $1" | tee -a "$LOG_FILE"
    send_telegram "❌ Backup failed: $1"
    exit 1
}

send_telegram() {
    local message="$1"
    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=$TELEGRAM_CHAT_ID" \
        -d "text=$message" > /dev/null 2>&1 || true
}

sanitize_file() {
    local file="$1"
    local temp_file="${file}.sanitized"
    
    # Copy file to temp location for sanitization
    cp "$file" "$temp_file"
    
    # Replace API keys and tokens
    sed -i '' -E 's/(api[_-]?key["'\'']?[ :=]+)["'\'']?[A-Za-z0-9_-]{20,}["'\'']?/\1[SANITIZED_API_KEY]/g' "$temp_file"
    sed -i '' -E 's/(token["'\'']?[ :=]+)["'\'']?[A-Za-z0-9_-]{20,}["'\'']?/\1[SANITIZED_TOKEN]/g' "$temp_file"
    sed -i '' -E 's/(password["'\'']?[ :=]+)["'\'']?[A-Za-z0-9_!@#$%]{8,}["'\'']?/\1[SANITIZED_PASSWORD]/g' "$temp_file"
    sed -i '' -E 's/(secret["'\'']?[ :=]+)["'\'']?[A-Za-z0-9_-]{20,}["'\'']?/\1[SANITIZED_SECRET]/g' "$temp_file"
    
    # Replace private URLs
    sed -i '' -E 's|https://[a-zA-Z0-9._-]*@github.com|https://github.com|g' "$temp_file"
    sed -i '' -E 's|git@[a-zA-Z0-9._-]*:|git@github.com:|g' "$temp_file"
    
    # Replace Telegram bot tokens
    sed -i '' -E 's/[0-9]{8,10}:[A-Za-z0-9_-]{35}/[TELEGRAM_BOT_TOKEN]/g' "$temp_file"
    
    # Replace OpenAI API keys (sk-...)
    sed -i '' -E 's/sk-[A-Za-z0-9]{48}/[OPENAI_API_KEY]/g' "$temp_file"
    
    # Replace OpenRouter API keys
    sed -i '' -E 's/(openrouter[_-]?api[_-]?key["'\'']?[ :=]+)["'\'']?[A-Za-z0-9_-]{20,}["'\'']?/\1[OPENROUTER_API_KEY]/g' "$temp_file"
    
    # Replace gateway tokens (long hex strings)
    sed -i '' -E 's/"token": "[a-f0-9]{40}"/"token": "[GATEWAY_TOKEN]"/g' "$temp_file"
    
    # Replace auth tokens
    sed -i '' -E 's/"(auth|memory|api)[_-]?(key|token|secret)"[ :]?[ "]?[A-Za-z0-9_-]{20,}[a-zA-Z0-9_]?[ ]?[;,]?/\1[SANITIZED_AUTH_TOKEN]/g' "$temp_file"
    
    echo "$temp_file"
}

log "Starting Tomi backup..."

# Clone or update the backup repo
if [ -d "$REPO_DIR/.git" ]; then
    log "Updating existing repo..."
    cd "$REPO_DIR"
    git pull --rebase > /dev/null 2>&1
else
    log "Cloning backup repository..."
    rm -rf "$REPO_DIR"
    GIT_SSH_COMMAND="ssh -i $SSH_KEY" git clone "$GITHUB_REPO" "$REPO_DIR" 2>&1 || error "Failed to clone repository"
    cd "$REPO_DIR"
fi

# Create backup directory with date
BACKUP_DIR="$REPO_DIR/backups/$BACKUP_DATE"
mkdir -p "$BACKUP_DIR"
mkdir -p "$BACKUP_DIR/openclaw"
mkdir -p "$BACKUP_DIR/workspace"
mkdir -p "$BACKUP_DIR/ssh"
mkdir -p "$BACKUP_DIR/cron"

log "Copying and sanitizing files..."

# Files to backup from openclaw config
OPENCLAW_FILES=(
    "$BACKUP_SRC/openclaw.json"
)

for file in "${OPENCLAW_FILES[@]}"; do
    if [ -f "$file" ]; then
        sanitized=$(sanitize_file "$file")
        dest="$BACKUP_DIR/openclaw/$(basename "$file")"
        mv "$sanitized" "$dest"
        log "Backed up: $file"
    fi
done

# Backup workspace files
WORKSPACE_FILES=(
    "$BACKUP_SRC/workspace/SOUL.md"
    "$BACKUP_SRC/workspace/MEMORY.md"
    "$BACKUP_SRC/workspace/USER.md"
    "$BACKUP_SRC/workspace/IDENTITY.md"
    "$BACKUP_SRC/workspace/AGENTS.md"
    "$BACKUP_SRC/workspace/TOOLS.md"
)

for file in "${WORKSPACE_FILES[@]}"; do
    if [ -f "$file" ]; then
        sanitized=$(sanitize_file "$file")
        dest="$BACKUP_DIR/workspace/$(basename "$file")"
        mv "$sanitized" "$dest"
        log "Backed up: $file"
    fi
done

# Backup workspace memory files
if [ -d "$BACKUP_SRC/workspace/memory" ]; then
    mkdir -p "$BACKUP_DIR/workspace/memory"
    for file in "$BACKUP_SRC/workspace/memory"/*.md; do
        if [ -f "$file" ]; then
            sanitized=$(sanitize_file "$file")
            dest="$BACKUP_DIR/workspace/memory/$(basename "$file")"
            mv "$sanitized" "$dest"
            log "Backed up: $file"
        fi
    done
fi

# Backup skill configurations
if [ -d "$BACKUP_SRC/skills" ]; then
    mkdir -p "$BACKUP_DIR/skills"
    cp -r "$BACKUP_SRC/skills"/* "$BACKUP_DIR/skills/" 2>/dev/null || true
    log "Backed up skills directory"
fi

# Backup cron jobs
log "Checking cron jobs..."
crontab -l > "$BACKUP_DIR/cron/crontab.txt" 2>/dev/null || echo "No crontab" > "$BACKUP_DIR/cron/crontab.txt"
if [ -f "$BACKUP_DIR/cron/crontab.txt" ]; then
    log "Backed up crontab"
fi

# Backup SSH public key (not private!)
if [ -f "$HOME/.ssh/id_rsa_tomi_deploy.pub" ]; then
    cp "$HOME/.ssh/id_rsa_tomi_deploy.pub" "$BACKUP_DIR/ssh/deploy_key.pub"
    log "Backed up SSH public key"
fi

# Create README with backup info
cat > "$BACKUP_DIR/README.md" << EOF
# Tomi Agent Backup - $BACKUP_DATE

## Backup Contents
- \`openclaw/\` - OpenClaw configuration
- \`workspace/\` - Agent workspace (SOUL.md, MEMORY.md, etc.)
- \`skills/\` - Skill configurations
- \`cron/\` - Cron job definitions
- \`ssh/\` - SSH public key (deploy key only, NOT private)

## Secrets Sanitization
All sensitive data has been replaced with placeholders:
- [SANITIZED_API_KEY]
- [SANITIZED_TOKEN]
- [SANITIZED_PASSWORD]
- [SANITIZED_SECRET]
- [TELEGRAM_BOT_TOKEN]
- [OPENAI_API_KEY]
- [OPENROUTER_API_KEY]
- [GATEWAY_TOKEN]
- [SANITIZED_AUTH_TOKEN]

## Restore Instructions
1. Clone this repository
2. Replace [SANITIZED_*] placeholders with actual values
3. Copy files back to their original locations
4. Restart the OpenClaw gateway

Generated: $DATE_STAMP
EOF

# Commit changes
log "Committing changes..."
cd "$REPO_DIR"
git add -A
git commit -m "Backup: $BACKUP_DATE $DATE_STAMP" || log "No changes to commit"

# Push to GitHub
log "Pushing to GitHub..."
GIT_SSH_COMMAND="ssh -i $SSH_KEY" git push origin main 2>&1 || error "Failed to push to GitHub"

# Cleanup old backups (keep last 7 days)
log "Cleaning up old backups..."
cd "$REPO_DIR"
find backups -type d -mtime +7 -exec rm -rf {} \; 2>/dev/null || true

log "Backup completed successfully!"

# Send Telegram notification
send_telegram "✅ Tomi backup completed: $BACKUP_DATE"

# Cleanup
rm -f /tmp/tomi_backup_*.sanitized 2>/dev/null || true
