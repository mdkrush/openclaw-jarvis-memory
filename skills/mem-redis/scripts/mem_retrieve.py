#!/usr/bin/env python3
"""
Manual Retrieval: Get recent conversation turns from Redis buffer.

Use this when context has been compacted or you need to recall recent details.

Usage: python3 mem_retrieve.py [--limit 20] [--user-id rob]
"""

import os
import sys
import json
import redis
import argparse
from datetime import datetime, timezone

# Config
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
USER_ID = os.getenv("USER_ID", "rob")

def get_recent_turns(user_id, limit=20):
    """Get recent turns from Redis buffer."""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        key = f"mem:{user_id}"
        
        # Get most recent N items (0 to limit-1)
        items = r.lrange(key, 0, limit - 1)
        
        # Parse and reverse (so oldest first)
        turns = []
        for item in items:
            try:
                turn = json.loads(item)
                turns.append(turn)
            except json.JSONDecodeError:
                continue
        
        # Reverse to chronological order
        turns.reverse()
        
        return turns
    except Exception as e:
        print(f"Error reading from Redis: {e}", file=sys.stderr)
        return []

def format_turn(turn):
    """Format a turn for display."""
    role = turn.get('role', 'unknown')
    content = turn.get('content', '')
    turn_num = turn.get('turn', '?')
    
    # Truncate long content
    if len(content) > 500:
        content = content[:500] + "..."
    
    role_icon = "👤" if role == 'user' else "🤖"
    return f"{role_icon} Turn {turn_num} ({role}):\n{content}\n"

def main():
    parser = argparse.ArgumentParser(description="Retrieve recent turns from mem buffer")
    parser.add_argument("--user-id", default=USER_ID, help="User ID")
    parser.add_argument("--limit", type=int, default=20, help="Number of turns to retrieve")
    args = parser.parse_args()
    
    # Get turns
    turns = get_recent_turns(args.user_id, args.limit)
    
    if not turns:
        print(f"No recent turns in memory buffer (mem:{args.user_id})")
        print("\nPossible reasons:")
        print("  - Heartbeat hasn't run yet")
        print("  - Cron already backed up and cleared Redis")
        print("  - Redis connection issue")
        sys.exit(0)
    
    # Display
    print(f"=== Recent {len(turns)} Turn(s) from Memory Buffer ===\n")
    for turn in turns:
        print(format_turn(turn))
    
    print(f"\nBuffer key: mem:{args.user_id}")
    print("Note: These turns are also in Redis until daily cron backs them up to Qdrant.")

if __name__ == "__main__":
    main()
