#!/usr/bin/env python3
"""
Add a task to the queue.
Usage: python3 add_task.py "Task description" [options]
"""

import redis
import sys
import time
import os
import argparse

REDIS_HOST = os.environ.get("REDIS_HOST", "10.0.0.36")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)

def get_redis():
    return redis.Redis(
        host=REDIS_HOST, 
        port=REDIS_PORT, 
        password=REDIS_PASSWORD,
        decode_responses=True
    )

def generate_task_id():
    return f"task_{int(time.time())}_{os.urandom(4).hex()[:8]}"

def add_task(description, task_type="default", priority="medium", created_by="Kimi", message=None, command=None):
    r = get_redis()
    
    task_id = generate_task_id()
    timestamp = str(int(time.time()))
    
    # Build task data
    task_data = {
        "id": task_id,
        "description": description,
        "type": task_type,
        "status": "pending",
        "created_at": timestamp,
        "created_by": created_by,
        "priority": priority,
        "started_at": "",
        "completed_at": "",
        "result": ""
    }
    
    # Add type-specific fields
    if task_type == "notify" and message:
        task_data["message"] = message
    elif task_type == "command" and command:
        task_data["command"] = command
    
    # Store task details
    r.hset(f"task:{task_id}", mapping=task_data)
    
    # Add to pending queue
    # For priority: high=lpush (front), others=rpush (back)
    if priority == "high":
        r.lpush("tasks:pending", task_id)
    else:
        r.rpush("tasks:pending", task_id)
    
    print(f"[ADDED] {task_id}: {description} ({priority}, {task_type})")
    return task_id

def main():
    parser = argparse.ArgumentParser(description="Add a task to the queue")
    parser.add_argument("description", help="Task description")
    parser.add_argument("--type", choices=["default", "notify", "command"], 
                        default="default", help="Task type")
    parser.add_argument("--priority", choices=["high", "medium", "low"], 
                        default="medium", help="Task priority")
    parser.add_argument("--by", default="Kimi", help="Who created the task")
    parser.add_argument("--message", help="Message to send (for notify type)")
    parser.add_argument("--command", help="Shell command to run (for command type)")
    
    args = parser.parse_args()
    
    task_id = add_task(
        args.description, 
        args.type, 
        args.priority, 
        args.by,
        args.message,
        args.command
    )
    print(f"Task ID: {task_id}")

if __name__ == "__main__":
    main()
