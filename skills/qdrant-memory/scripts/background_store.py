#!/usr/bin/env python3
"""
Background Conversation Storage - Fire-and-forget wrapper (Mem0-style)

Usage:
    background_store.py "user_message" "ai_response" \
        --user-id "rob" \
        [--turn N] \
        [--session-id UUID]

Zero delay for user - storage happens asynchronously.
Mem0-style: user_id is REQUIRED (persistent across all chats).
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
AUTO_STORE = SCRIPT_DIR / "auto_store.py"

def store_in_background(
    user_id: str,
    user_message: str, 
    ai_response: str, 
    turn: int = None, 
    session_id: str = None
):
    """Fire off storage without waiting - returns immediately"""
    
    cmd = [
        sys.executable,
        str(AUTO_STORE),
        user_message,
        ai_response,
        "--user-id", user_id
    ]
    
    if turn:
        cmd.extend(["--turn", str(turn)])
    
    if session_id:
        cmd.extend(["--session-id", session_id])
    
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
        description="Store conversation in background (Mem0-style, zero delay)"
    )
    parser.add_argument("user_message", help="User's message")
    parser.add_argument("ai_response", help="AI's response")
    parser.add_argument("--user-id", required=True,
                        help="REQUIRED: Persistent user ID (e.g., 'rob')")
    parser.add_argument("--turn", type=int, help="Turn number")
    parser.add_argument("--session-id", help="Optional session/chat ID")
    
    args = parser.parse_args()
    
    store_in_background(
        user_id=args.user_id,
        user_message=args.user_message,
        ai_response=args.ai_response,
        turn=args.turn,
        session_id=args.session_id
    )

if __name__ == "__main__":
    main()
