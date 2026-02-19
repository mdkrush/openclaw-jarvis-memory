#!/usr/bin/env python3
"""
Mem0-Style Conversation Retrieval - User-centric memory search

Retrieves memories by USER, not by session/chat.
Cross-conversation search across all of Rob's memories.

Usage:
    # Search user's memories across all conversations
    python3 scripts/get_conversation_context.py --user-id "rob" "what was the decision about Qdrant?"
    
    # Get specific conversation
    python3 scripts/get_conversation_context.py --user-id "rob" --conversation-id <id>
    
    # Get all conversations for user
    python3 scripts/get_conversation_context.py --user-id "rob" --limit 50

Mem0-style: Memories belong to USER, not to session.
"""

import argparse
import json
import sys
import urllib.request
from datetime import datetime
from typing import List, Optional, Dict, Any

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "kimi_memories"
OLLAMA_URL = "http://10.0.0.10:11434/v1"

def get_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding using snowflake-arctic-embed2"""
    data = json.dumps({
        "model": "snowflake-arctic-embed2",
        "input": text[:8192]
    }).encode()
    
    req = urllib.request.Request(
        f"{OLLAMA_URL}/embeddings",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            return result["data"][0]["embedding"]
    except Exception as e:
        print(f"[Retrieval] Embedding error: {e}", file=sys.stderr)
        return None

def search_user_memories(user_id: str, query: str, limit: int = 10) -> List[Dict]:
    """
    MEM0-STYLE: Search memories for a specific user across all conversations.
    NOT session-based - user-centric.
    """
    embedding = get_embedding(query)
    if embedding is None:
        return []
    
    # Search with user_id filter (MEM0: memories belong to user)
    search_data = json.dumps({
        "vector": embedding,
        "limit": limit,
        "with_payload": True,
        "filter": {
            "must": [
                {"key": "user_id", "match": {"value": user_id}},
                {"key": "source_type", "match": {"value": "system"}}  # Search summaries
            ]
        }
    }).encode()
    
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/search",
        data=search_data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            return result.get("result", [])
    except Exception as e:
        print(f"[Retrieval] Search error: {e}", file=sys.stderr)
        return []

def get_user_conversations(user_id: str, limit: int = 100) -> List[Dict]:
    """Get all conversations for a user (Mem0-style)"""
    
    scroll_data = json.dumps({
        "limit": limit,
        "with_payload": True,
        "filter": {
            "must": [
                {"key": "user_id", "match": {"value": user_id}},
                {"key": "source_type", "match": {"value": "system"}}  # Get summaries
            ]
        }
    }).encode()
    
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
        data=scroll_data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            return result.get("result", {}).get("points", [])
    except Exception as e:
        print(f"[Retrieval] Fetch error: {e}", file=sys.stderr)
        return []

def get_conversation_by_id(user_id: str, conversation_id: str, limit: int = 100) -> List[Dict]:
    """Get full conversation by ID (with user verification)"""
    
    scroll_data = json.dumps({
        "limit": limit,
        "with_payload": True,
        "filter": {
            "must": [
                {"key": "user_id", "match": {"value": user_id}},
                {"key": "conversation_id", "match": {"value": conversation_id}}
            ]
        }
    }).encode()
    
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
        data=scroll_data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            return result.get("result", {}).get("points", [])
    except Exception as e:
        print(f"[Retrieval] Fetch error: {e}", file=sys.stderr)
        return []

def format_conversation(points: List[Dict]) -> str:
    """Format conversation into readable transcript"""
    
    def sort_key(p):
        turn = p.get("payload", {}).get("turn_number", 0)
        source = p.get("payload", {}).get("source_type", "")
        return (turn, 0 if source in ["user", "assistant"] else 1)
    
    sorted_points = sorted(points, key=sort_key)
    
    output = []
    current_turn = 0
    
    for point in sorted_points:
        payload = point.get("payload", {})
        text = payload.get("text", "")
        source = payload.get("source_type", "unknown")
        turn = payload.get("turn_number", 0)
        date = payload.get("date", "unknown")
        user = payload.get("user_id", "unknown")
        
        if payload.get("source") == "conversation_summary":
            continue
        
        if turn != current_turn:
            output.append(f"\n--- Turn {turn} [{date}] ---")
            current_turn = turn
        
        output.append(text)
    
    return "\n".join(output)

def main():
    parser = argparse.ArgumentParser(
        description="Mem0-style conversation retrieval (user-centric)"
    )
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--user-id", required=True,
                        help="REQUIRED: User ID (e.g., 'rob')")
    parser.add_argument("--conversation-id", 
                        help="Get specific conversation")
    parser.add_argument("--limit", type=int, default=10, 
                        help="Max results")
    parser.add_argument("--format", choices=["transcript", "json"], 
                       default="transcript")
    
    args = parser.parse_args()
    
    if not args.user_id:
        print("❌ --user-id is required for Mem0-style retrieval", file=sys.stderr)
        sys.exit(1)
    
    points = []
    
    if args.conversation_id:
        print(f"🔍 Fetching conversation for user '{args.user_id}': {args.conversation_id}")
        points = get_conversation_by_id(args.user_id, args.conversation_id, args.limit * 3)
    
    elif args.query:
        print(f"🔍 Searching memories for user '{args.user_id}': {args.query}")
        points = search_user_memories(args.user_id, args.query, args.limit)
    
    else:
        print(f"🔍 Fetching all memories for user '{args.user_id}'")
        points = get_user_conversations(args.user_id, args.limit)
    
    if not points:
        print(f"❌ No memories found for user '{args.user_id}'")
        sys.exit(1)
    
    if args.format == "json":
        print(json.dumps(points, indent=2))
    else:
        # Group by conversation_id
        conversations = {}
        for p in points:
            convo_id = p.get("payload", {}).get("conversation_id")
            if convo_id not in conversations:
                conversations[convo_id] = []
            conversations[convo_id].append(p)
        
        for i, (convo_id, convo_points) in enumerate(conversations.items(), 1):
            print(f"\n{'='*60}")
            print(f"📜 Conversation {i}: {convo_id}")
            print(f"{'='*60}")
            print(format_conversation(convo_points))

if __name__ == "__main__":
    main()
