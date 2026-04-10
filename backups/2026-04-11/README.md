# Tomi Agent Backup - 2026-04-11

## Backup Contents
- `openclaw/` - OpenClaw configuration
- `workspace/` - Agent workspace (SOUL.md, MEMORY.md, etc.)
- `skills/` - Skill configurations
- `cron/` - Cron job definitions
- `ssh/` - SSH public key (deploy key only, NOT private)

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

Generated: 2026-04-11 04:00:18
