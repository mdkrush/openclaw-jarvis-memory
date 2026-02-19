#!/usr/bin/env python3
"""
Heartbeat: Append new conversation turns to Redis short-term buffer.

This script runs during heartbeat to capture recent conversation context
before it gets compacted away. Stores in Redis until daily cron backs up to Qdrant.

Usage: python3 hb_append.py [--user-id rob]
"""

import os
import sys
import json
import redis
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Config
REDIS_HOST = os.getenv("REDIS_HOST", "10.0.0.36")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
USER_ID = os.getenv("USER_ID", "rob")

# Paths
WORKSPACE = Path("/root/.openclaw/workspace")
MEMORY_DIR = WORKSPACE / "memory"
SESSIONS_DIR = Path("/root/.openclaw/agents/main/sessions")
STATE_FILE = WORKSPACE / ".mem_last_turn"

def get_session_transcript():
    """Find the current session JSONL file."""
    files = list(SESSIONS_DIR.glob("*.jsonl"))
    if not files:
        return None
    # Get most recently modified
    return max(files, key=lambda p: p.stat().st_mtime)

def parse_turns_since(last_turn_num):
    """Extract conversation turns since last processed."""
    transcript_file = get_session_transcript()
    if not transcript_file or not transcript_file.exists():
        return []
    
    turns = []
    turn_counter = last_turn_num
    try:
        with open(transcript_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # OpenClaw format: {"type": "message", "message": {"role": "...", ...}}
                    if entry.get('type') == 'message' and 'message' in entry:
                        msg = entry['message']
                        role = msg.get('role')
                        
                        # Skip tool results for memory storage
                        if role == 'toolResult':
                            continue
                            
                        # Get content from message content array or string
                        content = ""
                        if isinstance(msg.get('content'), list):
                            # Extract text from content array
                            for item in msg['content']:
                                if isinstance(item, dict):
                                    if 'text' in item:
                                        content += item['text']
                                    elif 'thinking' in item:
                                        content += f"[thinking: {item['thinking'][:200]}...]"
                        elif isinstance(msg.get('content'), str):
                            content = msg['content']
                        
                        if content and role in ('user', 'assistant'):
                            turn_counter += 1
                            turns.append({
                                'turn': turn_counter,
                                'role': role,
                                'content': content[:2000],
                                'timestamp': entry.get('timestamp', datetime.now(timezone.utc).isoformat()),
                                'user_id': USER_ID,
                                'session': str(transcript_file.name).replace('.jsonl', '')
                            })
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error reading transcript: {e}", file=sys.stderr)
        return []
    
    return turns

def get_last_turn():
    """Get last turn number from state file."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return int(f.read().strip())
        except:
            pass
    return 0

def save_last_turn(turn_num):
    """Save last turn number to state file."""
    try:
        with open(STATE_FILE, 'w') as f:
            f.write(str(turn_num))
    except Exception as e:
        print(f"Warning: Could not save state: {e}", file=sys.stderr)

def append_to_redis(turns, user_id):
    """Append turns to Redis list."""
    if not turns:
        return 0
    
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        key = f"mem:{user_id}"
        
        # Add all turns to list (LPUSH puts newest at front)
        for turn in turns:
            r.lpush(key, json.dumps(turn))
        
        return len(turns)
    except Exception as e:
        print(f"Error writing to Redis: {e}", file=sys.stderr)
        return 0

def main():
    parser = argparse.ArgumentParser(description="Append new turns to Redis mem buffer")
    parser.add_argument("--user-id", default=USER_ID, help="User ID for key naming")
    args = parser.parse_args()
    
    # Get last processed turn
    last_turn = get_last_turn()
    
    # Get new turns
    new_turns = parse_turns_since(last_turn)
    
    if not new_turns:
        print(f"No new turns since turn {last_turn}")
        sys.exit(0)
    
    # Append to Redis
    count = append_to_redis(new_turns, args.user_id)
    
    if count > 0:
        # Update last turn tracker
        max_turn = max(t['turn'] for t in new_turns)
        save_last_turn(max_turn)
        print(f"✅ Appended {count} turns to Redis (mem:{args.user_id})")
    else:
        print("❌ Failed to append to Redis")
        sys.exit(1)

if __name__ == "__main__":
    main()
