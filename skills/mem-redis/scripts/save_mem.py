#!/usr/bin/env python3
"""
Save all conversation context to Redis (not just new turns).

Unlike hb_append.py which only saves NEW turns since last run,
this script saves ALL context from the session (or resets and saves fresh).

Usage: python3 save_mem.py [--user-id rob] [--reset]
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
SESSIONS_DIR = Path("/root/.openclaw/agents/main/sessions")
STATE_FILE = WORKSPACE / ".mem_last_turn"

def get_session_transcript():
    """Find the current session JSONL file."""
    files = list(SESSIONS_DIR.glob("*.jsonl"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)

def parse_all_turns():
    """Extract ALL conversation turns from current session."""
    transcript_file = get_session_transcript()
    if not transcript_file or not transcript_file.exists():
        return []
    
    turns = []
    turn_counter = 0
    try:
        with open(transcript_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get('type') == 'message' and 'message' in entry:
                        msg = entry['message']
                        role = msg.get('role')
                        
                        if role == 'toolResult':
                            continue
                            
                        content = ""
                        if isinstance(msg.get('content'), list):
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

def save_to_redis(turns, user_id, reset=False):
    """Save turns to Redis. If reset, clear existing first."""
    if not turns:
        return 0
    
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        key = f"mem:{user_id}"
        
        # Clear existing if reset
        if reset:
            r.delete(key)
            print(f"Cleared existing Redis buffer ({key})")
        
        # Add all turns (LPUSH puts newest at front, so we reverse to keep order)
        for turn in reversed(turns):
            r.lpush(key, json.dumps(turn))
        
        return len(turns)
    except Exception as e:
        print(f"Error writing to Redis: {e}", file=sys.stderr)
        return 0

def update_state(last_turn_num):
    """Update last turn tracker."""
    try:
        with open(STATE_FILE, 'w') as f:
            f.write(str(last_turn_num))
    except Exception as e:
        print(f"Warning: Could not save state: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Save all conversation context to Redis")
    parser.add_argument("--user-id", default=USER_ID, help="User ID for key naming")
    parser.add_argument("--reset", action="store_true", help="Clear existing buffer first")
    args = parser.parse_args()
    
    # Get all turns
    turns = parse_all_turns()
    
    if not turns:
        print("No conversation turns found in session")
        sys.exit(0)
    
    # Save to Redis
    count = save_to_redis(turns, args.user_id, reset=args.reset)
    
    if count > 0:
        # Update state to track last turn
        max_turn = max(t['turn'] for t in turns)
        update_state(max_turn)
        
        action = "Reset and saved" if args.reset else "Saved"
        print(f"✅ {action} {count} turns to Redis (mem:{args.user_id})")
        print(f"   State updated to turn {max_turn}")
    else:
        print("❌ Failed to save to Redis")
        sys.exit(1)

if __name__ == "__main__":
    main()
