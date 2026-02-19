#!/usr/bin/env python3
"""
Lightweight notification checker for agent messages
Cron job: Check Redis stream hourly, notify if new messages
"""

import json
import redis
import os
from datetime import datetime, timezone

REDIS_HOST = "10.0.0.36"
REDIS_PORT = 6379
STREAM_NAME = "agent-messages"
LAST_NOTIFIED_KEY = "agent:notifications:last_id"

# Simple stdout notification (OpenClaw captures stdout for alerts)
def notify(messages):
    if not messages:
        return
    
    other_agent = messages[0].get("agent", "Agent")
    count = len(messages)
    
    # Single line notification - minimal tokens
    print(f"📨 {other_agent}: {count} new message(s) in agent-messages")
    
    # Optional: preview first message (uncomment if wanted)
    # if messages:
    #     preview = messages[0].get("message", "")[:50]
    #     print(f"   Latest: {preview}...")

def check_notifications():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    
    # Get last position we notified about
    last_id = r.get(LAST_NOTIFIED_KEY) or "0"
    
    # Read new messages since last notification
    result = r.xread({STREAM_NAME: last_id}, block=100, count=100)
    
    if not result:
        return  # No new messages, silent exit
    
    messages = []
    new_last_id = last_id
    
    for stream_name, entries in result:
        for msg_id, data in entries:
            messages.append(data)
            new_last_id = msg_id
    
    if messages:
        # Filter out our own messages (don't notify about messages we sent)
        my_agent = os.environ.get("AGENT_NAME", "Kimi")  # Set in cron env
        other_messages = [m for m in messages if m.get("agent") != my_agent]
        
        if other_messages:
            notify(other_messages)
        
        # Update last notified position regardless
        r.set(LAST_NOTIFIED_KEY, new_last_id)

if __name__ == "__main__":
    check_notifications()
