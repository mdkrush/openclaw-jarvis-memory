#!/usr/bin/env python3
"""
Create today's memory file if it doesn't exist
Usage: create_daily_memory.py [date]
"""

import sys
import os
from datetime import datetime, timezone

def get_cst_date():
    """Get current date in CST (America/Chicago)"""
    from datetime import datetime, timezone
    import time
    
    # CST is UTC-6 (standard time) or UTC-5 (daylight time)
    # Use a simple approximation: check if DST is active
    now = datetime.now(timezone.utc)
    
    # Convert to approximate CST (this is a simplified version)
    # For production, use pytz or zoneinfo
    is_dst = time.localtime().tm_isdst > 0
    offset = -5 if is_dst else -6  # CDT or CST
    
    cst_now = now.replace(hour=(now.hour + offset) % 24)
    return cst_now.strftime('%Y-%m-%d')

def create_daily_memory(date_str=None):
    """Create memory file for the given date"""
    if date_str is None:
        date_str = get_cst_date()
    
    memory_dir = "/root/.openclaw/workspace/memory"
    filepath = os.path.join(memory_dir, f"{date_str}.md")
    
    # Ensure directory exists
    os.makedirs(memory_dir, exist_ok=True)
    
    # Check if file already exists
    if os.path.exists(filepath):
        print(f"✅ Memory file already exists: {filepath}")
        return filepath
    
    # Create new daily memory file
    content = f"""# {date_str} — Daily Memory Log

## Session Start
- **Date:** {date_str}
- **Agent:** Kimi

## Activities

*(Log activities, decisions, and important context here)*

## Notes

---
*Stored for long-term memory retention*
"""
    
    try:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"✅ Created memory file: {filepath}")
        return filepath
    except Exception as e:
        print(f"❌ Error creating memory file: {e}")
        return None

if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    create_daily_memory(date_arg)
