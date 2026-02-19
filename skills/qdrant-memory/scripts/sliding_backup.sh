#!/bin/bash
# Daily Conversation Backup - 7-Day Sliding Window
# Processes last 7 days to catch any missed conversations

SCRIPT_DIR="/root/.openclaw/workspace/skills/qdrant-memory"
LOG_FILE="/var/log/qdrant-daily-backup.log"

echo "==============================================" >> "$LOG_FILE"
echo "7-Day Sliding Window Backup - $(date)" >> "$LOG_FILE"
echo "==============================================" >> "$LOG_FILE"

# Process last 7 days
for day_offset in -6 -5 -4 -3 -2 -1 0; do
    date_str=$(date -d "$day_offset days ago" +%Y-%m-%d)
    echo "Processing: $date_str..." >> "$LOG_FILE"
    cd "$SCRIPT_DIR" && python3 scripts/daily_conversation_backup.py "$date_str" >> "$LOG_FILE" 2>&1
done

echo "Backup complete at $(date)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
