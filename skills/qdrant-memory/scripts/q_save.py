#!/usr/bin/env python3
"""
Q Save - Trigger conversation storage (Mem0-style)

Usage:
    q_save.py --user-id "rob" "User message" "AI response" [--turn N]

Called when user says "save q" or "q save" to immediately
store the current conversation to Qdrant.

Mem0-style: user_id is REQUIRED and persistent across all chats.
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
BACKGROUND_STORE = SCRIPT_DIR / "background_store.py"

def q_save(
    user_id: str,
    user_message: str, 
    ai_response: str, 
    turn: int = None
):
    """Save conversation to Qdrant (background, zero delay)"""
    
    cmd = [
        sys.executable,
        str(BACKGROUND_STORE),
        user_message,
        ai_response,
        "--user-id", user_id
    ]
    
    if turn:
        cmd.extend(["--turn", str(turn)])
    
    # Fire and forget
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description='Q Save - Mem0-style trigger (user-centric)'
    )
    parser.add_argument("--user-id", required=True,
                        help="REQUIRED: User ID (e.g., 'rob')")
    parser.add_argument("user_message", help="User's message")
    parser.add_argument("ai_response", help="AI's response")
    parser.add_argument("--turn", type=int, help="Turn number")
    
    args = parser.parse_args()
    
    if q_save(args.user_id, args.user_message, args.ai_response, args.turn):
        print(f"✅ Saved for user '{args.user_id}'")
    else:
        print("❌ Failed to save", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
