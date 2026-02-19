#!/usr/bin/env python3
"""
Auto Conversation Memory - TRUE Mem0-style Full Context Storage

User-centric memory - all conversations link to persistent user_id.
NOT session/chat-centric like old version.

Features:
- Persistent user_id (e.g., "rob") across all conversations
- Cross-conversation retrieval (find memories from any chat)
- Automatic conversation threading
- Deduplication
- Mem0-style: memories belong to USER, not to session

Usage:
    python3 scripts/auto_store.py "user_message" "ai_response" \
        --user-id "rob" \
        --conversation-id <uuid> \
        --turn <n>

Mem0 Architecture:
    - user_id: "rob" (persistent across all your chats)
    - conversation_id: Groups turns within one conversation
    - session_id: Optional - tracks specific chat instance
    - Retrieved by: user_id + semantic similarity (NOT session_id)
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.request
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "kimi_memories"
OLLAMA_URL = "http://10.0.0.10:11434/v1"

# In-memory cache for deduplication (per process)
_recent_hashes = set()

def get_content_hash(user_msg: str, ai_response: str) -> str:
    """Generate hash for deduplication"""
    content = f"{user_msg.strip()}::{ai_response.strip()}"
    return hashlib.md5(content.encode()).hexdigest()

def is_duplicate(user_id: str, user_msg: str, ai_response: str) -> bool:
    """
    Check if this conversation turn already exists for this user.
    Uses: user_id + content_hash
    """
    content_hash = get_content_hash(user_msg, ai_response)
    
    # Check in-memory cache first
    if content_hash in _recent_hashes:
        return True
    
    # Check Qdrant for existing entry with this user_id + content_hash
    try:
        search_body = {
            "filter": {
                "must": [
                    {"key": "user_id", "match": {"value": user_id}},
                    {"key": "content_hash", "match": {"value": content_hash}}
                ]
            },
            "limit": 1,
            "with_payload": False
        }
        
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
            data=json.dumps(search_body).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            points = result.get("result", {}).get("points", [])
            if len(points) > 0:
                return True
    except Exception:
        pass
    
    return False

def mark_stored(user_msg: str, ai_response: str):
    """Mark content as stored in memory cache"""
    content_hash = get_content_hash(user_msg, ai_response)
    _recent_hashes.add(content_hash)
    if len(_recent_hashes) > 1000:
        _recent_hashes.clear()

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
        print(f"[AutoMemory] Embedding error: {e}", file=sys.stderr)
        return None

def generate_conversation_summary(user_msg: str, ai_response: str) -> str:
    """Generate a searchable summary of the conversation turn"""
    summary = f"Q: {user_msg[:200]} A: {ai_response[:300]}"
    return summary

def store_memory_point(
    user_id: str,
    text: str,
    speaker: str,
    date_str: str,
    conversation_id: str,
    turn_number: int,
    session_id: Optional[str],
    tags: List[str],
    importance: str = "medium",
    content_hash: Optional[str] = None
) -> Optional[str]:
    """Store a single memory point to Qdrant with user_id"""
    
    embedding = get_embedding(text)
    if embedding is None:
        return None
    
    point_id = str(uuid.uuid4())
    
    payload = {
        # MEM0-STYLE: user_id is PRIMARY key
        "user_id": user_id,
        "text": text,
        "date": date_str,
        "tags": tags,
        "importance": importance,
        "source": "conversation_auto",
        "source_type": "user" if speaker == "user" else "assistant",
        "category": "Full Conversation",
        "confidence": "high",
        "verified": True,
        "created_at": datetime.now().isoformat(),
        "access_count": 0,
        "last_accessed": datetime.now().isoformat(),
        "conversation_id": conversation_id,
        "turn_number": turn_number,
        "session_id": session_id or ""
    }
    
    if content_hash:
        payload["content_hash"] = content_hash
    
    upsert_data = {
        "points": [{
            "id": point_id,
            "vector": embedding,
            "payload": payload
        }]
    }
    
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points?wait=true",
        data=json.dumps(upsert_data).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            if result.get("status") == "ok":
                return point_id
    except Exception as e:
        print(f"[AutoMemory] Storage error: {e}", file=sys.stderr)
    
    return None

def store_conversation_turn(
    user_id: str,
    user_message: str,
    ai_response: str,
    conversation_id: Optional[str] = None,
    turn_number: Optional[int] = None,
    session_id: Optional[str] = None,
    date_str: Optional[str] = None,
    skip_if_duplicate: bool = True
) -> Dict[str, Any]:
    """
    Store a full conversation turn to Qdrant (Mem0-style)
    
    Args:
        user_id: PERSISTENT user identifier (e.g., "rob") - REQUIRED
        user_message: User's message
        ai_response: AI's response
        conversation_id: Groups related turns (auto-generated if None)
        turn_number: Sequential turn number
        session_id: Optional chat session identifier
        date_str: Date in YYYY-MM-DD format
    
    Returns:
        dict with success status and memory IDs
    """
    if not user_id:
        raise ValueError("user_id is required for Mem0-style storage")
    
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Check for duplicates (per user)
    if skip_if_duplicate and is_duplicate(user_id, user_message, ai_response):
        return {
            "user_point_id": None,
            "ai_point_id": None,
            "user_id": user_id,
            "conversation_id": conversation_id or "",
            "turn_number": turn_number or 1,
            "success": True,
            "skipped": True
        }
    
    if conversation_id is None:
        conversation_id = str(uuid.uuid4())
    
    if turn_number is None:
        turn_number = 1
    
    # Tags include user_id for easy filtering
    tags = [
        "conversation",
        f"user:{user_id}",
        date_str
    ]
    
    if session_id:
        tags.append(f"session:{session_id[:8]}")
    
    # Determine importance
    importance = "high" if any(kw in (user_message + ai_response).lower() 
                               for kw in ["remember", "important", "always", "never", "rule"]) else "medium"
    
    content_hash = get_content_hash(user_message, ai_response)
    
    # Store user message
    user_text = f"[{user_id}]: {user_message}"
    user_id_point = store_memory_point(
        user_id=user_id,
        text=user_text,
        speaker="user",
        date_str=date_str,
        conversation_id=conversation_id,
        turn_number=turn_number,
        session_id=session_id,
        tags=tags + ["user-message"],
        importance=importance,
        content_hash=content_hash
    )
    
    # Store AI response
    ai_text = f"[Kimi]: {ai_response}"
    ai_id_point = store_memory_point(
        user_id=user_id,
        text=ai_text,
        speaker="assistant",
        date_str=date_str,
        conversation_id=conversation_id,
        turn_number=turn_number,
        session_id=session_id,
        tags=tags + ["ai-response"],
        importance=importance,
        content_hash=content_hash
    )
    
    # Store summary
    summary = generate_conversation_summary(user_message, ai_response)
    summary_text = f"[Turn {turn_number}] {summary}"
    
    summary_embedding = get_embedding(summary_text)
    if summary_embedding:
        summary_id = str(uuid.uuid4())
        summary_payload = {
            "user_id": user_id,
            "text": summary_text,
            "date": date_str,
            "tags": tags + ["summary", "combined"],
            "importance": importance,
            "source": "conversation_summary",
            "source_type": "system",
            "category": "Conversation Summary",
            "confidence": "high",
            "verified": True,
            "created_at": datetime.now().isoformat(),
            "access_count": 0,
            "last_accessed": datetime.now().isoformat(),
            "conversation_id": conversation_id,
            "turn_number": turn_number,
            "session_id": session_id or "",
            "content_hash": content_hash,
            "user_message": user_message[:500],
            "ai_response": ai_response[:800]
        }
        
        upsert_data = {
            "points": [{
                "id": summary_id,
                "vector": summary_embedding,
                "payload": summary_payload
            }]
        }
        
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points?wait=true",
            data=json.dumps(upsert_data).encode(),
            headers={"Content-Type": "application/json"},
            method="PUT"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                json.loads(response.read().decode())
        except Exception as e:
            print(f"[AutoMemory] Summary storage error: {e}", file=sys.stderr)
    
    # Mark as stored
    if user_id_point and ai_id_point:
        mark_stored(user_message, ai_response)
    
    return {
        "user_point_id": user_id_point,
        "ai_point_id": ai_id_point,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "turn_number": turn_number,
        "success": bool(user_id_point and ai_id_point),
        "skipped": False
    }

def main():
    parser = argparse.ArgumentParser(
        description="Auto-store conversation turns to Qdrant (TRUE Mem0-style with user_id)"
    )
    parser.add_argument("user_message", help="The user's message")
    parser.add_argument("ai_response", help="The AI's response")
    parser.add_argument("--user-id", required=True, 
                        help="REQUIRED: Persistent user ID (e.g., 'rob')")
    parser.add_argument("--conversation-id", 
                        help="Conversation ID for threading (auto-generated if not provided)")
    parser.add_argument("--turn", type=int, help="Turn number in conversation")
    parser.add_argument("--session-id", 
                        help="Optional: Session/chat instance ID")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                      help="Date in YYYY-MM-DD format")
    
    args = parser.parse_args()
    
    result = store_conversation_turn(
        user_id=args.user_id,
        user_message=args.user_message,
        ai_response=args.ai_response,
        conversation_id=args.conversation_id,
        turn_number=args.turn,
        session_id=args.session_id,
        date_str=args.date
    )
    
    if result.get("skipped"):
        print(f"⚡ Skipped duplicate (already stored for user {result['user_id']})")
    elif result["success"]:
        print(f"✅ Stored for user '{result['user_id']}' turn {result['turn_number']}")
        print(f"   Conversation: {result['conversation_id'][:8]}...")
    else:
        print("❌ Failed to store conversation", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
