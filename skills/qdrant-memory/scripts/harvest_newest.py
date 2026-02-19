#!/usr/bin/env python3
"""
Harvest session files by explicit list (newest first).
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

_recent_hashes = set()

def get_content_hash(user_msg: str, ai_response: str) -> str:
    content = f"{user_msg.strip()}::{ai_response.strip()}"
    return hashlib.md5(content.encode()).hexdigest()

def is_duplicate(user_id: str, content_hash: str) -> bool:
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
            if result.get("result", {}).get("points", []):
                return True
    except Exception:
        pass
    return False

def get_embedding(text: str) -> Optional[List[float]]:
    data = json.dumps({"model": "snowflake-arctic-embed2", "input": text[:8192]}).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/embeddings", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())["data"][0]["embedding"]
    except Exception:
        return None

def store_turn(user_id: str, user_msg: str, ai_response: str, date_str: str, 
               conversation_id: str, turn_number: int, session_id: str) -> bool:
    content_hash = get_content_hash(user_msg, ai_response)
    if is_duplicate(user_id, content_hash):
        return False  # Skipped (duplicate)
    
    user_emb = get_embedding(f"[{user_id}]: {user_msg}")
    ai_emb = get_embedding(f"[Kimi]: {ai_response}")
    summary_emb = get_embedding(f"Q: {user_msg[:200]} A: {ai_response[:300]}")
    
    if not all([user_emb, ai_emb, summary_emb]):
        return False
    
    tags = ["conversation", "harvested", f"user:{user_id}", date_str]
    importance = "high" if any(kw in (user_msg + ai_response).lower() for kw in ["remember", "important", "always", "never", "rule"]) else "medium"
    
    points = [
        {"id": str(uuid.uuid4()), "vector": user_emb, "payload": {
            "user_id": user_id, "text": f"[{user_id}]: {user_msg[:2000]}", "date": date_str,
            "tags": tags + ["user-message"], "importance": importance, "source": "session_harvest",
            "source_type": "user", "category": "Full Conversation", "confidence": "high",
            "conversation_id": conversation_id, "turn_number": turn_number, "session_id": session_id, "content_hash": content_hash
        }},
        {"id": str(uuid.uuid4()), "vector": ai_emb, "payload": {
            "user_id": user_id, "text": f"[Kimi]: {ai_response[:2000]}", "date": date_str,
            "tags": tags + ["ai-response"], "importance": importance, "source": "session_harvest",
            "source_type": "assistant", "category": "Full Conversation", "confidence": "high",
            "conversation_id": conversation_id, "turn_number": turn_number, "session_id": session_id, "content_hash": content_hash
        }},
        {"id": str(uuid.uuid4()), "vector": summary_emb, "payload": {
            "user_id": user_id, "text": f"[Turn {turn_number}] Q: {user_msg[:200]} A: {ai_response[:300]}", "date": date_str,
            "tags": tags + ["summary"], "importance": importance, "source": "session_harvest",
            "source_type": "system", "category": "Conversation Summary", "confidence": "high",
            "conversation_id": conversation_id, "turn_number": turn_number, "session_id": session_id,
            "content_hash": content_hash, "user_message": user_msg[:500], "ai_response": ai_response[:800]
        }}
    ]
    
    req = urllib.request.Request(f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points?wait=true",
        data=json.dumps({"points": points}).encode(), headers={"Content-Type": "application/json"}, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            if json.loads(response.read().decode()).get("status") == "ok":
                _recent_hashes.add(content_hash)
                return True
    except Exception:
        pass
    return False

def parse_and_store(filepath: Path, user_id: str) -> tuple:
    turns = []
    turn_num = 0
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get('type') != 'message' or 'message' not in entry:
                        continue
                    msg = entry['message']
                    role = msg.get('role')
                    if role == 'toolResult':
                        continue
                    content = ""
                    if isinstance(msg.get('content'), list):
                        for item in msg['content']:
                            if isinstance(item, dict) and 'text' in item:
                                content += item['text']
                    elif isinstance(msg.get('content'), str):
                        content = msg['content']
                    if content and role in ('user', 'assistant'):
                        turn_num += 1
                        ts = entry.get('timestamp', '')
                        turns.append({'turn': turn_num, 'role': role, 'content': content[:2000],
                                     'date': ts[:10] if ts else datetime.now().strftime("%Y-%m-%d")})
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
        return 0, 0
    
    stored, skipped = 0, 0
    conv_id = str(uuid.uuid4())
    i = 0
    while i < len(turns):
        if turns[i]['role'] == 'user':
            user_msg = turns[i]['content']
            ai_resp = ""
            if i + 1 < len(turns) and turns[i + 1]['role'] == 'assistant':
                ai_resp = turns[i + 1]['content']
                i += 2
            else:
                i += 1
            if user_msg and ai_resp:
                if store_turn(user_id, user_msg, ai_resp, turns[i-1]['date'] if i > 0 else "", conv_id, turns[i-1]['turn'] if i > 0 else 0, filepath.stem):
                    stored += 1
                else:
                    skipped += 1
        else:
            i += 1
    return stored, skipped

def main():
    parser = argparse.ArgumentParser(description="Harvest sessions by name")
    parser.add_argument("--user-id", default="rob")
    parser.add_argument("sessions", nargs="*", help="Session filenames to process")
    args = parser.parse_args()
    
    total_stored, total_skipped = 0, 0
    for i, name in enumerate(args.sessions, 1):
        path = SESSIONS_DIR / name
        if not path.exists():
            print(f"[{i}] Not found: {name}")
            continue
        print(f"[{i}] {name}")
        s, sk = parse_and_store(path, args.user_id)
        total_stored += s
        total_skipped += sk
        if s > 0:
            print(f"  Stored: {s}, Skipped: {sk}")
    
    print(f"\nTotal: {total_stored} stored, {total_skipped} skipped")

if __name__ == "__main__":
    main()
