# HEARTBEAT.md — Recurring Tasks

> Use step-3.5-flash:free model. Be concise. Silent unless something needs attention.

## Daily Schedule

### 8AM — Morning Brief
- Read yesterday's `memory/YYYY-MM-DD.md`
- Provide 3-bullet summary of unfinished tasks
- Check for any urgent emails or calendar items

### 12PM — Status Check
- Check for active project updates in workspace
- Verify cron job statuses (check for errors)
- Ensure memory is being flushed properly

### 6PM — Evening Flush
- Log key highlights from the day to today's `memory/YYYY-MM-DD.md`
- Check executioner logs for trading status
- Stay silent unless something needs immediate attention

## Weekly (Sunday)
- **Deep Distillation**: Review all daily logs from the past week
- Identify 3 major "lessons learned" 
- Add them to the "Wisdom" section of `MEMORY.md`
- Archive logs >7 days old if already distilled

## Response Rules

| Situation | Action |
|-----------|--------|
| Nothing urgent | Reply `HEARTBEAT_OK` only |
| Urgent email | Summarize & flag |
| Calendar conflict | Alert immediately |
| Trading error | Alert immediately |
| 3+ unfinished tasks | List them briefly |
| Weekly lessons | Summarize 3 key insights |

## Timing
- Run at scheduled times (8AM, 12PM, 6PM ICT)
- Respect quiet hours: 23:00 - 07:00 ICT
- Weekly distillation: Sunday 9AM ICT
