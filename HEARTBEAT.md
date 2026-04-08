# HEARTBEAT.md — Lightweight Daily Checks

> Run these checks silently. Only speak up if something needs attention.
> Use free model (step-3.5-flash:free). Be concise.

## What to Check

### 📧 Email (Gmail)
- Any urgent unread messages?
- Labels: [ lich bui / lichbt@gmail.com ]

### 📅 Calendar (Today + Tomorrow)
- Upcoming events in next 24-48h?
- Any conflicts or important meetings?

### 💼 Trading Portfolio Status
- Check executioner logs: `tail -50 /Users/lich/.openclaw/workspace-executioner/logs/*.log`
- Any open positions? P&L?

### 🔔 Notifications
- Any failed cron jobs?
- Any error logs in recent memory?

## Response Rules

| Situation | Action |
|-----------|--------|
| Nothing urgent | Reply `HEARTBEAT_OK` only |
| Urgent email | Summarize & flag |
| Calendar conflict | Alert immediately |
| Trading error | Alert immediately |
| Everything normal | Stay silent |

## Timing
- Run checks 2-3x per day (morning, afternoon, evening)
- Respect quiet hours: 23:00 - 07:00 ICT
- Rotate through checks, don't do all at once
