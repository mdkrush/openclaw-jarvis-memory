#!/usr/bin/env python3
"""
Quick user context for email replies.
Returns recent memory summary, not full conversations.
"""

import json
import sys
import urllib.request
from typing import Optional

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "kimi_memories"

def get_user_context(user_id: str, limit: int = 5) -> str:
    """Get recent context for user - returns formatted summary."""
    
    # Use scroll to get recent memories for user
    data = json.dumps({
        "limit": 10,  # Get more to find profile
        "with_payload": True,
        "filter": {
            "must": [
                {"key": "user_id", "match": {"value": user_id}}
            ]
        }
    }).encode()

    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            points = result.get("result", {}).get("points", [])

        if not points:
            return ""

        # Prioritize: 1) Profile info, 2) Recent user message, 3) Recent context
        profile = None
        recent_user = None
        recent_context = []

        for point in points:
            payload = point.get("payload", {})
            text = payload.get("text", "")
            source_type = payload.get("source_type", "")
            
            # Look for profile (contains "Profile" or key identifying info)
            if "profile" in text.lower() or "lives in" in text.lower():
                profile = text[:200]
            elif source_type == "user" and not recent_user:
                recent_user = text[:150]
            elif source_type in ["assistant", "system"]:
                clean = text.replace("\r\n", " ").replace("\n", " ")[:150]
                recent_context.append(clean)

        # Build output: profile first if exists, then recent context
        parts = []
        if profile:
            parts.append(f"[PROFILE] {profile}")
        if recent_user:
            parts.append(f"[USER] {recent_user}")
        if recent_context:
            parts.append(f"[CONTEXT] {recent_context[0][:100]}")

        return " || ".join(parts) if parts else ""

    except Exception as e:
        return ""

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Get quick user context")
    parser.add_argument("--user-id", required=True, help="User ID")
    parser.add_argument("--limit", type=int, default=5, help="Max memories")
    args = parser.parse_args()

    context = get_user_context(args.user_id, args.limit)
    if context:
        print(context)