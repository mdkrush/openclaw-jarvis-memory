#!/usr/bin/env python3
"""
Daily Conversation Backup - Store day's conversations to Qdrant (Mem0-style)

Reads the daily memory file and stores all conversation turns to Qdrant
as full context (Mem0-style) with persistent user_id. Run at 3:30am daily.

Usage:
    daily_conversation_backup.py [YYYY-MM-DD]
    # If no date provided, processes yesterday's log

Mem0-style: All conversations linked to persistent user_id.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "kimi_memories"
OLLAMA_URL = "http://10.0.0.10:11434/v1"
MEMORY_DIR = "/root/.openclaw/workspace/memory"

# DEFAULT USER - Mem0-style: memories belong to user
DEFAULT_USER_ID = "rob"

def get_content_hash(user_msg: str, ai_response: str) -> str:
    """Generate hash for deduplication"""
    content = f"{user_msg.strip()}::{ai_response.strip()}"
    return hashlib.md5(content.encode()).hexdigest()

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
        print(f"[DailyBackup] Embedding error: {e}", file=sys.stderr)
        return None

def is_duplicate(user_id: str, content_hash: str) -> bool:
    """Check if already stored for this user"""
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
            return len(points) > 0
    except Exception:
        pass
    return False

def parse_daily_log(date_str: str) -> List[Dict[str, str]]:
    """Parse the daily memory file into conversation turns"""
    log_file = os.path.join(MEMORY_DIR, f"{date_str}.md")
    
    if not os.path.exists(log_file):
        print(f"[DailyBackup] No log file found for {date_str}")
        return []
    
    with open(log_file, 'r') as f:
        content = f.read()
    
    conversations = []
    turn_number = 0
    
    # Split by headers (## [timestamp] ...)
    sections = re.split(r'\n##\s+', content)
    
    for section in sections:
        if not section.strip():
            continue
        
        lines = section.strip().split('\n')
        if not lines:
            continue
        
        header = lines[0]
        body = '\n'.join(lines[1:]).strip()
        
        # Extract user message from header
        user_match = re.search(r'\[.*?\]\s*(.+)', header)
        if user_match:
            user_msg = user_match.group(1)
        else:
            user_msg = header
        
        # Extract AI response
        ai_match = re.search(r'(?:Kimi|Assistant|AI)[:\s]+(.+?)(?=\n##|\Z)', body, re.DOTALL | re.IGNORECASE)
        if ai_match:
            ai_response = ai_match.group(1).strip()
        else:
            paragraphs = body.split('\n\n')
            if len(paragraphs) > 1:
                ai_response = '\n\n'.join(paragraphs[1:]).strip()
            else:
                ai_response = body
        
        if user_msg and ai_response:
            turn_number += 1
            conversations.append({
                'user': user_msg,
                'ai': ai_response,
                'turn_number': turn_number,
                'date': date_str
            })
    
    return conversations

def store_conversation_turn(
    user_id: str,
    user_message: str,
    ai_response: str,
    conversation_id: str,
    turn_number: int,
    date_str: str
) -> bool:
    """Store a single conversation turn to Qdrant (Mem0-style)"""
    
    content_hash = get_content_hash(user_message, ai_response)
    
    # Check duplicate
    if is_duplicate(user_id, content_hash):
        return True  # Already stored, skip silently
    
    # Generate embeddings
    user_embedding = get_embedding(user_message)
    ai_embedding = get_embedding(ai_response)
    summary = f"Q: {user_message[:200]}... A: {ai_response[:300]}..."
    summary_embedding = get_embedding(summary)
    
    if not all([user_embedding, ai_embedding, summary_embedding]):
        return False
    
    tags = ["conversation", "daily-backup", date_str, f"user:{user_id}"]
    importance = "high" if any(kw in (user_message + ai_response).lower() 
                               for kw in ["remember", "important", "always", "never", "rule", "decision"]) else "medium"
    
    points = []
    
    # User message
    user_id_point = str(uuid.uuid4())
    points.append({
        "id": user_id_point,
        "vector": user_embedding,
        "payload": {
            "user_id": user_id,
            "text": f"[{user_id}]: {user_message}",
            "date": date_str,
            "tags": tags + ["user-message"],
            "importance": importance,
            "source": "conversation_daily_backup",
            "source_type": "user",
            "category": "Full Conversation",
            "confidence": "high",
            "verified": True,
            "created_at": datetime.now().isoformat(),
            "access_count": 0,
            "last_accessed": datetime.now().isoformat(),
            "conversation_id": conversation_id,
            "turn_number": turn_number,
            "content_hash": content_hash
        }
    })
    
    # AI response
    ai_id = str(uuid.uuid4())
    points.append({
        "id": ai_id,
        "vector": ai_embedding,
        "payload": {
            "user_id": user_id,
            "text": f"[Kimi]: {ai_response}",
            "date": date_str,
            "tags": tags + ["ai-response"],
            "importance": importance,
            "source": "conversation_daily_backup",
            "source_type": "assistant",
            "category": "Full Conversation",
            "confidence": "high",
            "verified": True,
            "created_at": datetime.now().isoformat(),
            "access_count": 0,
            "last_accessed": datetime.now().isoformat(),
            "conversation_id": conversation_id,
            "turn_number": turn_number,
            "content_hash": content_hash
        }
    })
    
    # Summary
    summary_id = str(uuid.uuid4())
    points.append({
        "id": summary_id,
        "vector": summary_embedding,
        "payload": {
            "user_id": user_id,
            "text": f"[Turn {turn_number}] {summary}",
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
            "content_hash": content_hash,
            "user_message": user_message[:500],
            "ai_response": ai_response[:800]
        }
    })
    
    # Upload to Qdrant
    upsert_data = {"points": points}
    
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points?wait=true",
        data=json.dumps(upsert_data).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            return result.get("status") == "ok"
    except Exception as e:
        print(f"[DailyBackup] Storage error: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Daily conversation backup to Qdrant (Mem0-style)"
    )
    parser.add_argument(
        "date",
        nargs="?",
        help="Date to process (YYYY-MM-DD). Default: yesterday"
    )
    parser.add_argument(
        "--user-id",
        default=DEFAULT_USER_ID,
        help=f"User ID (default: {DEFAULT_USER_ID})"
    )
    
    args = parser.parse_args()
    
    if args.date:
        date_str = args.date
    else:
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")
    
    user_id = args.user_id
    
    print(f"📅 Processing daily log for {date_str} (user: {user_id})...")
    
    conversations = parse_daily_log(date_str)
    
    if not conversations:
        print(f"⚠️  No conversations found for {date_str}")
        sys.exit(0)
    
    print(f"📝 Found {len(conversations)} conversation turns")
    
    stored = 0
    skipped = 0
    failed = 0
    
    for conv in conversations:
        conversation_id = str(uuid.uuid4())
        
        content_hash = get_content_hash(conv['user'], conv['ai'])
        if is_duplicate(user_id, content_hash):
            skipped += 1
            print(f"  ⏭️  Turn {conv['turn_number']} skipped (duplicate)")
            continue
        
        success = store_conversation_turn(
            user_id=user_id,
            user_message=conv['user'],
            ai_response=conv['ai'],
            conversation_id=conversation_id,
            turn_number=conv['turn_number'],
            date_str=date_str
        )
        
        if success:
            stored += 1
            print(f"  ✅ Turn {conv['turn_number']} stored")
        else:
            failed += 1
            print(f"  ❌ Turn {conv['turn_number']} failed")
    
    print(f"\n{'='*50}")
    print(f"Daily backup complete for {date_str} (user: {user_id}):")
    print(f"  Stored: {stored} turns ({stored * 3} embeddings)")
    print(f"  Skipped: {skipped} turns (duplicates)")
    print(f"  Failed: {failed} turns")
    
    if stored > 0:
        print(f"\n✅ Daily backup: {stored} conversations stored to Qdrant")
    
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
