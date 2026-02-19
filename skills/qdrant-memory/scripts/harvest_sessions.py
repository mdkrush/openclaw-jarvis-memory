#!/usr/bin/env python3
"""
Harvest all session JSONL files and store to Qdrant.

Scans all session files, extracts conversation turns, and stores to Qdrant
with proper user_id and deduplication.

Usage: python3 harvest_sessions.py [--user-id rob] [--dry-run]
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "kimi_memories"
OLLAMA_URL = "http://10.0.0.10:11434/v1"
SESSIONS_DIR = Path("/root/.openclaw/agents/main/sessions")

# In-memory cache for deduplication
_recent_hashes = set()

def get_content_hash(user_msg: str, ai_response: str) -> str:
    """Generate hash for deduplication"""
    content = f"{user_msg.strip()}::{ai_response.strip()}"
    return hashlib.md5(content.encode()).hexdigest()

def is_duplicate(user_id: str, content_hash: str) -> bool:
    """Check if this content already exists for this user"""
    if content_hash in _recent_hashes:
        return True
    
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
        print(f"[Harvest] Embedding error: {e}", file=sys.stderr)
        return None

def store_turn(user_id: str, user_msg: str, ai_response: str, 
               date_str: str, conversation_id: str, turn_number: int,
               session_id: str, dry_run: bool = False) -> Dict:
    """Store a single conversation turn to Qdrant"""
    
    content_hash = get_content_hash(user_msg, ai_response)
    
    # Check duplicate
    if is_duplicate(user_id, content_hash):
        return {"skipped": True, "reason": "duplicate"}
    
    if dry_run:
        return {"skipped": False, "dry_run": True}
    
    # Generate embeddings
    user_embedding = get_embedding(f"[{user_id}]: {user_msg}")
    ai_embedding = get_embedding(f"[Kimi]: {ai_response}")
    summary = f"Q: {user_msg[:200]} A: {ai_response[:300]}..."
    summary_embedding = get_embedding(summary)
    
    if not all([user_embedding, ai_embedding, summary_embedding]):
        return {"skipped": True, "reason": "embedding_failed"}
    
    tags = ["conversation", "harvested", f"user:{user_id}", date_str]
    importance = "high" if any(kw in (user_msg + ai_response).lower() 
                               for kw in ["remember", "important", "always", "never", "rule"]) else "medium"
    
    points = []
    
    # User message
    points.append({
        "id": str(uuid.uuid4()),
        "vector": user_embedding,
        "payload": {
            "user_id": user_id,
            "text": f"[{user_id}]: {user_msg[:2000]}",
            "date": date_str,
            "tags": tags + ["user-message"],
            "importance": importance,
            "source": "session_harvest",
            "source_type": "user",
            "category": "Full Conversation",
            "confidence": "high",
            "verified": True,
            "created_at": datetime.now().isoformat(),
            "conversation_id": conversation_id,
            "turn_number": turn_number,
            "session_id": session_id,
            "content_hash": content_hash
        }
    })
    
    # AI response
    points.append({
        "id": str(uuid.uuid4()),
        "vector": ai_embedding,
        "payload": {
            "user_id": user_id,
            "text": f"[Kimi]: {ai_response[:2000]}",
            "date": date_str,
            "tags": tags + ["ai-response"],
            "importance": importance,
            "source": "session_harvest",
            "source_type": "assistant",
            "category": "Full Conversation",
            "confidence": "high",
            "verified": True,
            "created_at": datetime.now().isoformat(),
            "conversation_id": conversation_id,
            "turn_number": turn_number,
            "session_id": session_id,
            "content_hash": content_hash
        }
    })
    
    # Summary
    if summary_embedding:
        points.append({
            "id": str(uuid.uuid4()),
            "vector": summary_embedding,
            "payload": {
                "user_id": user_id,
                "text": f"[Turn {turn_number}] {summary}",
                "date": date_str,
                "tags": tags + ["summary"],
                "importance": importance,
                "source": "session_harvest_summary",
                "source_type": "system",
                "category": "Conversation Summary",
                "confidence": "high",
                "verified": True,
                "created_at": datetime.now().isoformat(),
                "conversation_id": conversation_id,
                "turn_number": turn_number,
                "session_id": session_id,
                "content_hash": content_hash,
                "user_message": user_msg[:500],
                "ai_response": ai_response[:800]
            }
        })
    
    # Upload
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
            if result.get("status") == "ok":
                _recent_hashes.add(content_hash)
                return {"skipped": False, "stored": True}
    except Exception as e:
        print(f"[Harvest] Storage error: {e}", file=sys.stderr)
    
    return {"skipped": True, "reason": "upload_failed"}

def parse_session_file(filepath: Path) -> List[Dict]:
    """Parse a session JSONL file and extract conversation turns"""
    turns = []
    turn_number = 0
    
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get('type') == 'message' and 'message' in entry:
                        msg = entry['message']
                        role = msg.get('role')
                        
                        if role == 'toolResult':
                            continue
                        
                        content = ""
                        if isinstance(msg.get('content'), list):
                            for item in msg['content']:
                                if isinstance(item, dict):
                                    if 'text' in item:
                                        content += item['text']
                                    elif 'thinking' in item:
                                        content += f"[thinking: {item['thinking'][:200]}...]"
                        elif isinstance(msg.get('content'), str):
                            content = msg['content']
                        
                        if content and role in ('user', 'assistant'):
                            turn_number += 1
                            timestamp = entry.get('timestamp', '')
                            date_str = timestamp[:10] if timestamp else datetime.now().strftime("%Y-%m-%d")
                            
                            turns.append({
                                'turn': turn_number,
                                'role': role,
                                'content': content[:2000],
                                'date': date_str,
                                'session': filepath.stem
                            })
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"[Harvest] Error reading {filepath}: {e}", file=sys.stderr)
    
    return turns

def main():
    parser = argparse.ArgumentParser(description="Harvest session files to Qdrant")
    parser.add_argument("--user-id", default="yourname", help="User ID for storage")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually store")
    parser.add_argument("--limit", type=int, default=0, help="Limit sessions (0=all)")
    args = parser.parse_args()
    
    # Find all session files
    session_files = sorted(SESSIONS_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    
    if args.limit > 0:
        session_files = session_files[:args.limit]
    
    print(f"Found {len(session_files)} session files")
    
    total_stored = 0
    total_skipped = 0
    total_failed = 0
    
    for i, session_file in enumerate(session_files, 1):
        print(f"\n[{i}/{len(session_files)}] Processing: {session_file.name}")
        
        turns = parse_session_file(session_file)
        if not turns:
            print("  No turns found")
            continue
        
        print(f"  Found {len(turns)} turns")
        
        # Pair user messages with AI responses
        conversation_id = str(uuid.uuid4())
        j = 0
        while j < len(turns):
            turn = turns[j]
            
            if turn['role'] == 'user':
                user_msg = turn['content']
                ai_response = ""
                
                # Look for next AI response
                if j + 1 < len(turns) and turns[j + 1]['role'] == 'assistant':
                    ai_response = turns[j + 1]['content']
                    j += 2
                else:
                    j += 1
                
                if user_msg and ai_response:
                    result = store_turn(
                        user_id=args.user_id,
                        user_msg=user_msg,
                        ai_response=ai_response,
                        date_str=turn['date'],
                        conversation_id=conversation_id,
                        turn_number=turn['turn'],
                        session_id=turn['session'],
                        dry_run=args.dry_run
                    )
                    
                    if result.get("skipped"):
                        if result.get("reason") == "duplicate":
                            total_skipped += 1
                        else:
                            total_failed += 1
                    else:
                        total_stored += 1
                        if total_stored % 10 == 0:
                            print(f"  Progress: {total_stored} stored, {total_skipped} skipped")
            else:
                j += 1
    
    print(f"\n{'='*50}")
    print(f"Harvest complete:")
    print(f"  Stored: {total_stored} turns ({total_stored * 3} embeddings)")
    print(f"  Skipped (duplicates): {total_skipped}")
    print(f"  Failed: {total_failed}")
    
    if args.dry_run:
        print("\n[DRY RUN] Nothing was actually stored")

if __name__ == "__main__":
    main()