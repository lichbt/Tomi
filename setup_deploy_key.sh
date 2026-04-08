#!/bin/bash
# Setup GitHub Deploy Key for backup repository

set -e

echo "Setting up GitHub Deploy Key for backup repository..."
echo ""

REPO_OWNER="lichbt"
REPO_NAME="Tomi"
KEY_NAME="OpenClaw Backup Deploy Key"
KEY_FILE="$HOME/.ssh/id_ed25519_${REPO_NAME}_deploy"

# Check for existing deploy key
if [ -f "$KEY_FILE" ]; then
    echo "Existing deploy key found: $KEY_FILE"
    echo ""
    read -p "Regenerate new deploy key? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Using existing deploy key."
        echo ""
        echo "Public key:"
        cat "${KEY_FILE}.pub"
        exit 0
    fi
fi

# Create .ssh directory if it doesn't exist
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Generate new deploy key (Ed25519)
echo "Generating new Ed25519 deploy key..."
ssh-keygen -t ed25519 -C "deploy-key+${REPO_NAME}@openclaw" -f "$KEY_FILE" -N ""

# Set proper permissions
chmod 600 "$KEY_FILE"
chmod 644 "${KEY_FILE}.pub"

echo ""
echo "Deploy key generated successfully!"
echo ""

# Display public key
echo "Your deploy key public key (add this to GitHub):"
echo "================================================"
cat "${KEY_FILE}.pub"
echo "================================================"
echo ""

# Instructions for adding to GitHub
echo "To add this deploy key to your GitHub repository:"
echo "1. Go to: https://github.com/${REPO_OWNER}/${REPO_NAME}/settings/keys"
echo "2. Click 'Add deploy key'"
echo "3. Title: '$KEY_NAME'"
echo "4. Key: Paste the above public key"
echo "5. ✅ Allow write access (IMPORTANT for pushing backups)"
echo "6. Click 'Add key'"
echo ""

# Create SSH config entry
echo "Creating SSH config entry..."
if [ ! -f ~/.ssh/config ]; then
    touch ~/.ssh/config
    chmod 600 ~/.ssh/config
fi

# Add deploy key config
if ! grep -q "github.com-${REPO_NAME}-deploy" ~/.ssh/config; then
    cat >> ~/.ssh/config << EOF

# GitHub deploy key for ${REPO_NAME} repository
Host github.com-${REPO_NAME}-deploy
    HostName github.com
    User git
    IdentityFile ${KEY_FILE}
    IdentitiesOnly yes
EOF
    echo "SSH config updated."
else
    echo "Deploy key entry already exists in SSH config."
fi

# Test SSH connection
echo ""
echo "Testing SSH connection with deploy key..."
ssh -T git@github.com-${REPO_NAME}-deploy 2>&1 | grep -i "successfully authenticated\|you've successfully authenticated"

if [ $? -eq 0 ]; then
    echo "SSH connection successful!"
else
    echo "Note: Deploy key needs to be added to GitHub first."
    echo "After adding the key to GitHub, test with:"
    echo "  ssh -T git@github.com-${REPO_NAME}-deploy"
fi

# Update backup script to use deploy key
echo ""
echo "Updating backup script to use deploy key..."
BACKUP_SCRIPT="/Users/lich/.openclaw/workspace/backup_agent_setup.sh"

if [ -f "$BACKUP_SCRIPT" ]; then
    # Update GIT_REPO to use deploy key host
    sed -i '' "s|GIT_REPO=\"git@github.com:lichbt/Tomi.git\"|GIT_REPO=\"git@github.com-${REPO_NAME}-deploy:lichbt/Tomi.git\"|" "$BACKUP_SCRIPT"
    
    # Update SSH key loading section
    sed -i '' "s|ssh-add ~/.ssh/id_ed25519_github|ssh-add ${KEY_FILE}|" "$BACKUP_SCRIPT"
    
    echo "Backup script updated to use deploy key."
fi

echo ""
echo "Setup complete! Summary:"
echo "1. Deploy key generated: $KEY_FILE"
echo "2. Public key ready to add to GitHub (shown above)"
echo "3. SSH config updated"
echo "4. Backup script configured to use deploy key"
echo ""
echo "Next steps:"
echo "1. Add the deploy key to your GitHub repository (with write access)"
echo "2. Test SSH connection: ssh -T git@github.com-${REPO_NAME}-deploy"
echo "3. Test backup script: ./backup_agent_setup.sh"
echo ""