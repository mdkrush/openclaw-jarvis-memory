#!/usr/bin/env python3
"""
List tasks in the queue - pending, active, and recent completed.
"""

import redis
import os
from datetime import datetime

REDIS_HOST = os.environ.get("REDIS_HOST", "10.0.0.36")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

def get_redis():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def format_time(timestamp):
    if not timestamp or timestamp == "0":
        return "-"
    try:
        dt = datetime.fromtimestamp(int(timestamp))
        return dt.strftime("%H:%M:%S")
    except:
        return timestamp

def show_tasks(r, key, title, status_filter=None, limit=10):
    task_ids = r.lrange(key, 0, limit - 1)
    
    if not task_ids:
        print(f"\n{title}: (empty)")
        return
    
    print(f"\n{title}:")
    print("-" * 80)
    
    for task_id in task_ids:
        task = r.hgetall(f"task:{task_id}")
        if not task:
            print(f"  {task_id}: [missing data]")
            continue
        
        status = task.get("status", "?")
        desc = task.get("description", "no description")[:50]
        priority = task.get("priority", "medium")
        created = format_time(task.get("created_at"))
        
        if status_filter and status != status_filter:
            continue
            
        print(f"  [{status:10}] {task_id} | {priority:6} | {created} | {desc}")

def main():
    r = get_redis()
    
    print("=" * 80)
    print("TASK QUEUE STATUS")
    print("=" * 80)
    
    # Show counts
    pending_count = r.llen("tasks:pending")
    active_count = r.llen("tasks:active")
    completed_count = r.llen("tasks:completed")
    
    print(f"\nCounts: {pending_count} pending | {active_count} active | {completed_count} completed")
    
    # Show pending
    show_tasks(r, "tasks:pending", "PENDING TASKS", limit=10)
    
    # Show active
    show_tasks(r, "tasks:active", "ACTIVE TASKS")
    
    # Show recent completed
    show_tasks(r, "tasks:completed", "RECENT COMPLETED (last 10)", limit=10)
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
