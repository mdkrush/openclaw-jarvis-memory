#!/usr/bin/env python3
"""
Convenience wrapper for activity logging
Add to your scripts: from log_activity import log_done, check_other_agent
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from activity_log import log_activity, check_for_duplicates, get_recent_activities

AGENT_NAME = "Kimi"  # Change to "Max" on that instance

def log_done(action_type: str, description: str, files=None, status="completed"):
    """
    Quick log of completed work
    
    Example:
        log_done("cron_created", "Set up daily OpenClaw repo monitoring", 
                 files=["/path/to/script.py"])
    """
    activity_id = log_activity(
        agent=AGENT_NAME,
        action_type=action_type,
        description=description,
        affected_files=files or [],
        status=status
    )
    print(f"[ActivityLog] Logged: {action_type} → {activity_id[:8]}...")
    return activity_id

def check_other_agent(action_type: str, keywords: str, hours: int = 6) -> bool:
    """
    Check if Max (or Kimi) already did this recently
    
    Example:
        if check_other_agent("cron_created", "openclaw repo monitoring"):
            print("Max already set this up!")
            return
    """
    other_agent = "Max" if AGENT_NAME == "Kimi" else "Kimi"
    
    recent = get_recent_activities(agent=other_agent, action_type=action_type, hours=hours)
    
    keywords_lower = keywords.lower().split()
    for activity in recent:
        desc = activity.get("description", "").lower()
        if all(kw in desc for kw in keywords_lower):
            print(f"[ActivityLog] ⚠️  {other_agent} already did this!")
            print(f"   When: {activity['timestamp'][:19]}")
            print(f"   What: {activity['description']}")
            return True
    
    return False

def show_recent_collaboration(hours: int = 24):
    """Show what both agents have been up to"""
    activities = get_recent_activities(hours=hours, limit=50)
    
    print(f"\n[ActivityLog] Both agents' work (last {hours}h):\n")
    for a in activities:
        agent = a['agent']
        icon = "🤖" if agent == "Max" else "🎙️"
        print(f"{icon} [{a['timestamp'][11:19]}] {agent}: {a['action_type']}")
        print(f"   {a['description']}")

if __name__ == "__main__":
    # Quick test
    print(f"Agent: {AGENT_NAME}")
    print("Functions available:")
    print("  log_done(action_type, description, files=[], status='completed')")
    print("  check_other_agent(action_type, keywords, hours=6)")
    print("  show_recent_collaboration(hours=24)")
    print()
    print("Recent activity:")
    show_recent_collaboration(hours=24)
