#!/usr/bin/env python3
"""
Check agent messages from Redis stream
Usage: agent_check.py [--list N] [--check] [--last-minutes M]
"""

import argparse
import sys
import json
import time
from datetime import datetime, timezone

# Add parent to path for imports
sys.path.insert(0, '/root/.openclaw/workspace/skills/qdrant-memory')

try:
    import redis
except ImportError:
    print("❌ Redis module not available")
    sys.exit(1)

REDIS_HOST = "10.0.0.36"
REDIS_PORT = 6379
STREAM_KEY = "agent-messages"
LAST_CHECKED_KEY = "agent:last_check_timestamp"

def get_redis_client():
    """Get Redis connection"""
    try:
        return redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return None

def get_messages_since(last_check=None, count=10):
    """Get messages from Redis stream since last check"""
    r = get_redis_client()
    if not r:
        return []
    
    try:
        # Get last N messages from stream
        messages = r.xrevrange(STREAM_KEY, count=count)
        
        result = []
        for msg_id, msg_data in messages:
            # Parse message data
            data = {}
            for k, v in msg_data.items():
                data[k] = v
            
            # Extract timestamp from message ID
            timestamp_ms = int(msg_id.split('-')[0])
            msg_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
            
            # Filter by last check if provided
            if last_check:
                if timestamp_ms <= last_check:
                    continue
            
            result.append({
                'id': msg_id,
                'time': msg_time,
                'data': data
            })
        
        return result
    except Exception as e:
        print(f"❌ Error reading stream: {e}")
        return []

def update_last_check():
    """Update the last check timestamp"""
    r = get_redis_client()
    if not r:
        return False
    
    try:
        now_ms = int(time.time() * 1000)
        r.set(LAST_CHECKED_KEY, str(now_ms))
        return True
    except Exception as e:
        print(f"❌ Error updating timestamp: {e}")
        return False

def get_last_check_time():
    """Get the last check timestamp"""
    r = get_redis_client()
    if not r:
        return None
    
    try:
        last = r.get(LAST_CHECKED_KEY)
        if last:
            return int(last)
        return None
    except:
        return None

def format_message(msg):
    """Format a message for display"""
    time_str = msg['time'].strftime('%Y-%m-%d %H:%M:%S UTC')
    data = msg['data']
    
    sender = data.get('sender', 'unknown')
    recipient = data.get('recipient', 'all')
    msg_type = data.get('type', 'message')
    content = data.get('content', '')
    
    return f"[{time_str}] {sender} → {recipient} ({msg_type}):\n  {content[:200]}{'...' if len(content) > 200 else ''}"

def main():
    parser = argparse.ArgumentParser(description="Check agent messages from Redis")
    parser.add_argument("--list", "-l", type=int, metavar="N", help="List last N messages")
    parser.add_argument("--check", "-c", action="store_true", help="Check for new messages since last check")
    parser.add_argument("--last-minutes", "-m", type=int, metavar="M", help="Check messages from last M minutes")
    parser.add_argument("--mark-read", action="store_true", help="Update last check timestamp after reading")
    
    args = parser.parse_args()
    
    if args.check:
        last_check = get_last_check_time()
        messages = get_messages_since(last_check)
        
        if messages:
            print(f"🔔 {len(messages)} new message(s):")
            for msg in reversed(messages):  # Oldest first
                print(format_message(msg))
                print()
        else:
            print("✅ No new messages")
        
        if args.mark_read:
            update_last_check()
            print("📌 Last check time updated")
    
    elif args.last_minutes:
        since_ms = int((time.time() - args.last_minutes * 60) * 1000)
        messages = get_messages_since(since_ms)
        
        if messages:
            print(f"📨 {len(messages)} message(s) from last {args.last_minutes} minutes:")
            for msg in reversed(messages):
                print(format_message(msg))
                print()
        else:
            print(f"✅ No messages in last {args.last_minutes} minutes")
    
    elif args.list:
        messages = get_messages_since(count=args.list)
        
        if messages:
            print(f"📜 Last {len(messages)} message(s):")
            for msg in reversed(messages):
                print(format_message(msg))
                print()
        else:
            print("📭 No messages in stream")
    
    else:
        # Default: check for new messages
        last_check = get_last_check_time()
        messages = get_messages_since(last_check)
        
        if messages:
            print(f"🔔 {len(messages)} new message(s):")
            for msg in reversed(messages):
                print(format_message(msg))
                print()
            update_last_check()
        else:
            print("✅ No new messages")

if __name__ == "__main__":
    main()
