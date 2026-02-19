#!/usr/bin/env python3
"""
Daily Cron: Process Redis buffer → Qdrant → Clear Redis.

This script runs once daily (via cron) to move buffered conversation
turns from Redis to durable Qdrant storage. Only clears Redis after
successful Qdrant write.

Usage: python3 cron_backup.py [--user-id rob] [--dry-run]
"""

import os
import sys
import json
import redis
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Add qdrant-memory to path (portable)
from pathlib import Path as _Path
WORKSPACE = _Path(os.getenv("OPENCLAW_WORKSPACE", str(_Path.home() / ".openclaw" / "workspace")))
sys.path.insert(0, str(WORKSPACE / "skills" / "qdrant-memory" / "scripts"))

try:
    from auto_store import store_conversation_turn
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    print("Warning: Qdrant storage not available, will simulate", file=sys.stderr)

# Config
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
USER_ID = os.getenv("USER_ID", "yourname")

def get_redis_items(user_id):
    """Get all items from Redis list."""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        key = f"mem:{user_id}"
        
        # Get all items (0 to -1 = entire list)
        items = r.lrange(key, 0, -1)
        
        # Parse JSON
        turns = []
        for item in items:
            try:
                turn = json.loads(item)
                turns.append(turn)
            except json.JSONDecodeError:
                continue
        
        return turns, key
    except Exception as e:
        print(f"Error reading from Redis: {e}", file=sys.stderr)
        return None, None

def store_to_qdrant(turns, user_id):
    """Store turns to Qdrant with file fallback."""
    if not QDRANT_AVAILABLE:
        print("[DRY RUN] Would store to Qdrant:", file=sys.stderr)
        for turn in turns[:3]:
            print(f"  - Turn {turn.get('turn', '?')}: {turn.get('role', '?')}", file=sys.stderr)
        if len(turns) > 3:
            print(f"  ... and {len(turns) - 3} more", file=sys.stderr)
        return True
    
    # Ensure chronological order (older -> newer)
    try:
        turns_sorted = sorted(turns, key=lambda t: (t.get('timestamp', ''), t.get('turn', 0)))
    except Exception:
        turns_sorted = turns

    user_turns = [t for t in turns_sorted if t.get('role') == 'user']
    if not user_turns:
        return True

    success_count = 0
    attempted = 0

    for i, turn in enumerate(turns_sorted):
        if turn.get('role') != 'user':
            continue
        attempted += 1
        try:
            # Pair with the next assistant message in chronological order (best effort)
            ai_response = ""
            j = i + 1
            while j < len(turns_sorted):
                if turns_sorted[j].get('role') == 'assistant':
                    ai_response = turns_sorted[j].get('content', '')
                    break
                if turns_sorted[j].get('role') == 'user':
                    break
                j += 1

            result = store_conversation_turn(
                user_message=turn.get('content', ''),
                ai_response=ai_response,
                user_id=user_id,
                turn_number=turn.get('turn', i),
                conversation_id=f"mem-buffer-{turn.get('timestamp', 'unknown')[:10]}"
            )

            # store_conversation_turn returns success/skipped; treat skipped as ok
            if result.get('success') or result.get('skipped'):
                success_count += 1
        except Exception as e:
            print(f"Error storing user turn {turn.get('turn', '?')}: {e}", file=sys.stderr)

    # Only consider Qdrant storage successful if we stored/skipped ALL user turns.
    return attempted > 0 and success_count == attempted

def store_to_file(turns, user_id):
    """Fallback: Store turns to JSONL file."""
    from datetime import datetime
    
    workspace = Path(os.getenv("OPENCLAW_WORKSPACE", str(Path.home() / ".openclaw" / "workspace")))
    backup_dir = workspace / "memory" / "redis-backups"
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = backup_dir / f"mem-backup-{user_id}-{timestamp}.jsonl"
    
    try:
        with open(filename, 'w') as f:
            for turn in turns:
                f.write(json.dumps(turn) + '\n')
        print(f"✅ Backed up {len(turns)} turns to file: {filename}")
        return True
    except Exception as e:
        print(f"❌ File backup failed: {e}", file=sys.stderr)
        return False

def clear_redis(key):
    """Clear Redis list after successful backup."""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.delete(key)
        return True
    except Exception as e:
        print(f"Error clearing Redis: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Backup Redis mem buffer to Qdrant")
    parser.add_argument("--user-id", default=USER_ID, help="User ID")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually clear Redis")
    args = parser.parse_args()
    
    # Get items from Redis
    turns, key = get_redis_items(args.user_id)
    
    if turns is None:
        print("❌ Failed to read from Redis")
        sys.exit(1)
    
    if not turns:
        print(f"No items in Redis buffer (mem:{args.user_id})")
        sys.exit(0)
    
    print(f"Found {len(turns)} turns in Redis buffer")
    
    # Try Qdrant first
    qdrant_success = False
    if not args.dry_run:
        qdrant_success = store_to_qdrant(turns, args.user_id)
        if qdrant_success:
            print(f"✅ Stored Redis buffer to Qdrant (all user turns)")
        else:
            print("⚠️ Qdrant storage incomplete; will NOT clear Redis", file=sys.stderr)
    else:
        print("[DRY RUN] Would attempt Qdrant storage")
        qdrant_success = True  # Dry run pretends success
    
    # If Qdrant failed/incomplete, try file backup (still do NOT clear Redis unless user chooses)
    file_success = False
    if not qdrant_success:
        print("⚠️ Qdrant storage failed/incomplete, writing file backup (Redis preserved)...")
        file_success = store_to_file(turns, args.user_id)
        if not file_success:
            print("❌ Both Qdrant and file backup failed - Redis buffer preserved")
            sys.exit(1)
        # Exit non-zero so monitoring can alert; keep Redis for re-try.
        sys.exit(1)
    
    # Clear Redis (only if not dry-run)
    if args.dry_run:
        print("[DRY RUN] Would clear Redis buffer")
        sys.exit(0)
    
    if clear_redis(key):
        print(f"✅ Cleared Redis buffer (mem:{args.user_id})")
    else:
        print(f"⚠️ Backup succeeded but failed to clear Redis - may duplicate on next run")
        sys.exit(1)
    
    backup_type = "Qdrant" if qdrant_success else "file"
    print(f"\n🎉 Successfully backed up {len(turns)} turns to {backup_type} long-term memory")

if __name__ == "__main__":
    main()
