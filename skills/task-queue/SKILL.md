# Task Queue Skill

Redis-based task queue for background jobs.

## What It Does

Queues and executes tasks via heartbeat worker.

## Commands

```bash
# Add a task
python3 scripts/add_task.py "Check disk space"

# List tasks
python3 scripts/list_tasks.py

# Execute (runs on heartbeat)
python3 scripts/heartbeat_worker.py
```

## Heartbeat Integration

Add to HEARTBEAT.md:
```bash
python3 /path/to/skills/task-queue/scripts/heartbeat_worker.py
```

## Files

- `add_task.py` - Add task to queue
- `list_tasks.py` - View queue status
- `heartbeat_worker.py` - Execute pending tasks
