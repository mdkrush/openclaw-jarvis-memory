# Memory Buffer Skill

Redis-based short-term memory buffer for OpenClaw.

## What It Does

Accumulates conversation turns in real-time and flushes to Qdrant daily.

## Commands

```bash
# Manual save (all turns)
python3 scripts/save_mem.py --user-id yourname

# Retrieve from buffer
python3 scripts/mem_retrieve.py --limit 10

# Search Redis + Qdrant
python3 scripts/search_mem.py "your query"
```

## Heartbeat Integration

Add to HEARTBEAT.md:
```bash
python3 /path/to/skills/mem-redis/scripts/hb_append.py
```

## Cron

```bash
# Daily flush at 3:00 AM
0 3 * * * python3 scripts/cron_backup.py
```

## Files

- `hb_append.py` - Heartbeat: append new turns only
- `save_mem.py` - Manual: save all turns
- `cron_backup.py` - Daily: flush to Qdrant
- `mem_retrieve.py` - Read from Redis
- `search_mem.py` - Search Redis + Qdrant
