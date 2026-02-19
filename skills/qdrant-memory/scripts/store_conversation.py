#!/usr/bin/env python3
"""
Conversation Memory Capture - Store conversational turns to Qdrant

This script stores the full conversational context (user messages + AI responses)
as atomic facts in Qdrant, not just summaries written to daily logs.

Usage:
    store_conversation.py "User message" "AI response" --date 2026-02-15 --tags "workflow"
    store_conversation.py --file conversation.json  # Batch mode

Features:
    - Stores both user queries and AI responses
    - Generates embeddings for semantic search
    - Links related turns with conversation IDs
    - Extracts facts from responses automatically
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "kimi_memories"
OLLAMA_URL = "http://localhost:11434/v1"


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
        print(f"Error generating embedding: {e}", file=sys.stderr)
        return None


def extract_tags(text: str, date_str: str) -> List[str]:
    """Extract relevant tags from text"""
    tags = ["conversation-turn", "atomic-fact", date_str]
    
    text_lower = text.lower()
    tag_mappings = {
        "youtube": "youtube",
        "video": "video",
        "workflow": "workflow",
        "process": "process",
        "qdrant": "qdrant",
        "memory": "memory",
        "fact": "facts",
        "extract": "extraction",
        "config": "configuration",
        "setting": "settings",
        "rule": "rules",
        "decision": "decisions",
        "preference": "preferences",
        "hardware": "hardware",
        "security": "security",
        "research": "research",
        "step": "steps",
        "grok": "grok",
        "thumbnail": "thumbnail",
        "title": "title",
        "description": "description",
        "seo": "seo",
        "tags": "tags",
    }
    
    for keyword, tag in tag_mappings.items():
        if keyword in text_lower:
            tags.append(tag)
    
    return list(set(tags))


def store_turn(
    speaker: str,
    message: str,
    date_str: str,
    tags: List[str] = None,
    conversation_id: str = None,
    turn_number: int = None,
    importance: str = "medium"
) -> Optional[str]:
    """Store a single conversational turn"""
    
    embedding = get_embedding(message)
    if embedding is None:
        return None
    
    point_id = str(uuid.uuid4())
    
    if tags is None:
        tags = extract_tags(message, date_str)
    
    payload = {
        "text": f"[{speaker}]: {message}",
        "date": date_str,
        "tags": tags,
        "importance": importance,
        "source": "conversation",
        "source_type": "user" if speaker == "Rob" else "assistant",
        "category": "Conversation",
        "confidence": "high",
        "verified": True,
        "created_at": datetime.now().isoformat(),
        "access_count": 0,
        "last_accessed": datetime.now().isoformat(),
        "conversation_id": conversation_id or str(uuid.uuid4()),
        "turn_number": turn_number or 0
    }
    
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
        print(f"Error storing turn: {e}", file=sys.stderr)
    
    return None


def store_conversation_pair(
    user_message: str,
    ai_response: str,
    date_str: str,
    tags: List[str] = None,
    importance: str = "medium"
) -> tuple:
    """Store both user query and AI response as linked turns"""
    
    conversation_id = str(uuid.uuid4())
    
    user_id = store_turn(
        speaker="Rob",
        message=user_message,
        date_str=date_str,
        tags=tags,
        conversation_id=conversation_id,
        turn_number=1,
        importance=importance
    )
    
    ai_id = store_turn(
        speaker="Kimi",
        message=ai_response,
        date_str=date_str,
        tags=tags,
        conversation_id=conversation_id,
        turn_number=2,
        importance=importance
    )
    
    return user_id, ai_id


def extract_facts_from_text(text: str, date_str: str) -> List[Dict[str, Any]]:
    """Extract atomic facts from a text block"""
    facts = []
    
    # Split into sentences
    sentences = [s.strip() for s in text.replace('. ', '.\n').split('\n') if s.strip()]
    
    for sentence in sentences:
        if len(sentence) < 10:
            continue
        
        embedding = get_embedding(sentence)
        if embedding is None:
            continue
        
        point_id = str(uuid.uuid4())
        
        facts.append({
            "id": point_id,
            "vector": embedding,
            "payload": {
                "text": sentence[:500],
                "date": date_str,
                "tags": extract_tags(sentence, date_str),
                "importance": "high" if "**" in sentence else "medium",
                "source": "fact-extraction",
                "source_type": "inferred",
                "category": "Extracted Fact",
                "confidence": "medium",
                "verified": False,
                "created_at": datetime.now().isoformat(),
                "access_count": 0,
                "last_accessed": datetime.now().isoformat()
            }
        })
    
    return facts


def main():
    parser = argparse.ArgumentParser(description="Store conversational turns to Qdrant")
    parser.add_argument("user_message", nargs="?", help="User's message/query")
    parser.add_argument("ai_response", nargs="?", help="AI's response")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Date (YYYY-MM-DD)")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--importance", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--file", help="JSON file with conversation array")
    parser.add_argument("--extract-facts", action="store_true", help="Also extract atomic facts from response")
    
    args = parser.parse_args()
    
    tags = args.tags.split(",") if args.tags else None
    
    if args.file:
        # Batch mode from JSON file
        with open(args.file, 'r') as f:
            conversations = json.load(f)
        
        total = 0
        for conv in conversations:
            user_id, ai_id = store_conversation_pair(
                conv["user"],
                conv["ai"],
                args.date,
                tags or conv.get("tags"),
                args.importance
            )
            if user_id and ai_id:
                total += 2
        
        print(f"✅ Stored {total} conversation turns")
    
    elif args.user_message and args.ai_response:
        # Single pair mode
        user_id, ai_id = store_conversation_pair(
            args.user_message,
            args.ai_response,
            args.date,
            tags,
            args.importance
        )
        
        if user_id and ai_id:
            print(f"✅ Stored conversation pair")
            print(f"   User turn: {user_id[:8]}...")
            print(f"   AI turn: {ai_id[:8]}...")
            
            if args.extract_facts:
                facts = extract_facts_from_text(args.ai_response, args.date)
                if facts:
                    # Upload facts
                    upsert_data = {"points": facts}
                    req = urllib.request.Request(
                        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points?wait=true",
                        data=json.dumps(upsert_data).encode(),
                        headers={"Content-Type": "application/json"},
                        method="PUT"
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=30) as response:
                            print(f"   Extracted {len(facts)} additional facts")
                    except Exception as e:
                        print(f"   Warning: Could not store extracted facts: {e}")
        else:
            print("❌ Failed to store conversation")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()