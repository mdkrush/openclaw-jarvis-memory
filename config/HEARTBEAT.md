# HEARTBEAT.md

# Keep this file empty (or with only comments) to skip heartbeat API calls.

# Add tasks below when you want the agent to check something periodically.

## Memory Buffer (Every Heartbeat)

Saves ALL current session context to Redis short-term buffer. Runs automatically.
Does NOT clear buffer — preserves turns from other sessions until daily backup.

```bash
python3 /root/.openclaw/workspace/skills/mem-redis/scripts/save_mem.py --user-id rob
```

Multiple sessions per day accumulate in Redis. Daily cron (3:00 AM) flushes everything to Qdrant.

## Email Check (Every Heartbeat)

Checks Gmail for messages from Rob or Jennifer. **Respond to any new emails found.**

```bash
python3 /root/.openclaw/workspace/skills/qdrant-memory/scripts/hb_check_email.py
```

**Authorized senders only:** `your_email@gmail.com`, `spouse_email@gmail.com`

*Edit `skills/qdrant-memory/scripts/hb_check_email.py` to set your authorized senders*

**When new email found:**
1. Read the email subject and body
2. Search Qdrant for relevant context about the topic
3. Respond to the email with a helpful reply
4. Store the email and your response to Qdrant for memory

---

## Manual Mode Only

All OTHER heartbeat actions are **manual only** when explicitly requested.

### When User Requests:
- **Check delayed notifications:** I will manually check the queue

### No Automatic Actions:
❌ Auto-sending notifications from queue
❌ Auto-logging heartbeat timestamps

## Available Manual Commands

```bash
# Check delayed notifications
redis-cli -h 10.0.0.36 LRANGE delayed:notifications 0 0

# Manual full context save to Redis (all current session turns)
python3 /root/.openclaw/workspace/skills/mem-redis/scripts/save_mem.py --user-id rob
```

## Daily Tasks

- Redis → Qdrant backup (cron 3:00 AM): `cron_backup.py`
- File-based backup (cron 3:30 AM): `sliding_backup.sh`

## Future Tasks (add as needed)
