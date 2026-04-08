#!/bin/bash
# Setup SSH key for GitHub backup repository

set -e

echo "Setting up SSH key for GitHub..."
echo ""

# Check for existing SSH keys
echo "Checking for existing SSH keys..."
if [ -d ~/.ssh ]; then
    echo "Existing SSH keys found:"
    ls -la ~/.ssh/
    
    # Check for GitHub-specific key
    if [ -f ~/.ssh/id_ed25519 ] || [ -f ~/.ssh/id_rsa ]; then
        echo ""
        read -p "Existing SSH keys found. Create new key for GitHub? (y/n): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Using existing SSH keys."
            exit 0
        fi
    fi
else
    echo "No .ssh directory found. Creating..."
    mkdir -p ~/.ssh
    chmod 700 ~/.ssh
fi

# Get email for key
echo ""
echo "Enter email address for SSH key (usually your GitHub email):"
read GITHUB_EMAIL

if [ -z "$GITHUB_EMAIL" ]; then
    echo "Error: Email address required."
    exit 1
fi

# Generate new SSH key (Ed25519 is recommended)
echo ""
echo "Generating new Ed25519 SSH key..."
ssh-keygen -t ed25519 -C "$GITHUB_EMAIL" -f ~/.ssh/id_ed25519_github -N ""

# Set proper permissions
chmod 600 ~/.ssh/id_ed25519_github
chmod 644 ~/.ssh/id_ed25519_github.pub

echo ""
echo "SSH key generated successfully!"
echo ""

# Display public key
echo "Your public key (add this to GitHub):"
echo "======================================"
cat ~/.ssh/id_ed25519_github.pub
echo "======================================"
echo ""

# Instructions for adding to GitHub
echo "To add this key to GitHub:"
echo "1. Go to https://github.com/settings/keys"
echo "2. Click 'New SSH key'"
echo "3. Give it a title (e.g., 'OpenClaw Backup')"
echo "4. Paste the above public key"
echo "5. Click 'Add SSH key'"
echo ""

# Test SSH connection
echo "Testing SSH connection to GitHub..."
ssh -T git@github.com -i ~/.ssh/id_ed25519_github 2>&1 | grep -i "successfully authenticated\|you've successfully authenticated"

if [ $? -eq 0 ]; then
    echo "SSH connection successful!"
else
    echo "SSH connection test completed. If you just added the key, it might take a moment to work."
fi

# Create SSH config for GitHub
echo ""
echo "Creating SSH config entry..."
if [ ! -f ~/.ssh/config ]; then
    touch ~/.ssh/config
    chmod 600 ~/.ssh/config
fi

# Add GitHub-specific config
if ! grep -q "github.com" ~/.ssh/config; then
    cat >> ~/.ssh/config << EOF

# GitHub for OpenClaw backup
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_github
    IdentitiesOnly yes
EOF
    echo "SSH config updated."
else
    echo "GitHub entry already exists in SSH config."
fi

# Update backup script to use this key
echo ""
echo "Updating backup script to use GitHub SSH key..."
BACKUP_SCRIPT="/Users/lich/.openclaw/workspace/backup_agent_setup.sh"

if [ -f "$BACKUP_SCRIPT" ]; then
    # Add SSH key loading to backup script
    sed -i '' 's|# Git operations|# Load SSH key for GitHub\neval "$(ssh-agent -s)" > /dev/null 2>&1\nssh-add ~/.ssh/id_ed25519_github > /dev/null 2>&1\n\n# Git operations|' "$BACKUP_SCRIPT"
    echo "Backup script updated."
fi

echo ""
echo "Setup complete! Next steps:"
echo "1. Add the public key to GitHub (shown above)"
echo "2. Test the backup script manually"
echo "3. Set up the cron job for 4:30am"
echo ""