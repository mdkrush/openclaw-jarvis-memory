#!/usr/bin/env python3
"""
Search memory: First Redis (exact), then Qdrant (semantic).

Usage: python3 search_mem.py "your search query" [--limit 10] [--user-id rob]

Searches:
1. Redis (mem:{user_id}) - exact text match in recent buffer
2. Qdrant (kimi_memories) - semantic similarity search
"""

import os
import sys
import json
import redis
import argparse
from pathlib import Path
from datetime import datetime

# Config
REDIS_HOST = os.getenv("REDIS_HOST", "10.0.0.36")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
USER_ID = os.getenv("USER_ID", "yourname")

QDRANT_URL = os.getenv("QDRANT_URL", "http://10.0.0.40:6333")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://10.0.0.10:11434/v1")

def search_redis(query, user_id, limit=20):
    """Search Redis buffer for exact text matches."""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        key = f"mem:{user_id}"
        
        # Get all items from list
        items = r.lrange(key, 0, -1)
        if not items:
            return []
        
        query_lower = query.lower()
        matches = []
        
        for item in items:
            try:
                turn = json.loads(item)
                content = turn.get('content', '').lower()
                if query_lower in content:
                    matches.append({
                        'source': 'redis',
                        'turn': turn.get('turn'),
                        'role': turn.get('role'),
                        'content': turn.get('content'),
                        'timestamp': turn.get('timestamp'),
                        'score': 'exact'
                    })
            except json.JSONDecodeError:
                continue
        
        # Sort by turn number descending (newest first)
        matches.sort(key=lambda x: x.get('turn', 0), reverse=True)
        return matches[:limit]
    except Exception as e:
        print(f"Redis search error: {e}", file=sys.stderr)
        return []

def get_embedding(text):
    """Get embedding from Ollama."""
    import urllib.request
    
    payload = json.dumps({
        "model": "snowflake-arctic-embed2",
        "input": text
    }).encode()
    
    req = urllib.request.Request(
        f"{OLLAMA_URL}/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return result.get('data', [{}])[0].get('embedding')
    except Exception as e:
        print(f"Embedding error: {e}", file=sys.stderr)
        return None

def search_qdrant(query, user_id, limit=10):
    """Search Qdrant for semantic similarity."""
    import urllib.request
    
    embedding = get_embedding(query)
    if not embedding:
        return []
    
    payload = json.dumps({
        "vector": embedding,
        "limit": limit,
        "with_payload": True,
        "filter": {
            "must": [
                {"key": "user_id", "match": {"value": user_id}}
            ]
        }
    }).encode()
    
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/kimi_memories/points/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            points = result.get('result', [])
            
            matches = []
            for point in points:
                payload = point.get('payload', {})
                matches.append({
                    'source': 'qdrant',
                    'score': round(point.get('score', 0), 3),
                    'turn': payload.get('turn_number'),
                    'role': payload.get('role'),
                    'content': payload.get('user_message') or payload.get('content', ''),
                    'ai_response': payload.get('ai_response', ''),
                    'timestamp': payload.get('timestamp'),
                    'conversation_id': payload.get('conversation_id')
                })
            return matches
    except Exception as e:
        print(f"Qdrant search error: {e}", file=sys.stderr)
        return []

def format_result(result, index):
    """Format a single search result."""
    source = result.get('source', 'unknown')
    role = result.get('role', 'unknown')
    turn = result.get('turn', '?')
    score = result.get('score', '?')
    
    content = result.get('content', '')
    if len(content) > 200:
        content = content[:200] + "..."
    
    # Role emoji
    role_emoji = "👤" if role == "user" else "🤖"
    
    # Source indicator
    source_icon = "🔴" if source == "redis" else "🔵"
    
    lines = [
        f"{source_icon} [{index}] Turn {turn} ({role}):",
        f"   {role_emoji} {content}"
    ]
    
    if source == "qdrant" and result.get('ai_response'):
        ai_resp = result['ai_response'][:150]
        if len(result['ai_response']) > 150:
            ai_resp += "..."
        lines.append(f"   💬 AI: {ai_resp}")
    
    if score != 'exact':
        lines.append(f"   📊 Score: {score}")
    else:
        lines.append(f"   📊 Match: exact (Redis)")
    
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Search memory: Redis first, then Qdrant")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--limit", type=int, default=10, help="Results per source (default: 10)")
    parser.add_argument("--user-id", default=USER_ID, help="User ID")
    parser.add_argument("--redis-only", action="store_true", help="Only search Redis")
    parser.add_argument("--qdrant-only", action="store_true", help="Only search Qdrant")
    args = parser.parse_args()
    
    print(f"🔍 Searching for: \"{args.query}\"\n")
    
    all_results = []
    
    # Search Redis first (unless qdrant-only)
    if not args.qdrant_only:
        print("📍 Searching Redis (exact match)...")
        redis_results = search_redis(args.query, args.user_id, limit=args.limit)
        if redis_results:
            print(f"✅ Found {len(redis_results)} matches in Redis\n")
            all_results.extend(redis_results)
        else:
            print("❌ No exact matches in Redis\n")
    
    # Search Qdrant (unless redis-only)
    if not args.redis_only:
        print("🧠 Searching Qdrant (semantic similarity)...")
        qdrant_results = search_qdrant(args.query, args.user_id, limit=args.limit)
        if qdrant_results:
            print(f"✅ Found {len(qdrant_results)} matches in Qdrant\n")
            all_results.extend(qdrant_results)
        else:
            print("❌ No semantic matches in Qdrant\n")
    
    # Display results
    if not all_results:
        print("No results found in either Redis or Qdrant.")
        sys.exit(0)
    
    print(f"=== Search Results ({len(all_results)} total) ===\n")
    
    # Sort: Redis first (chronological), then Qdrant (by score)
    redis_sorted = [r for r in all_results if r['source'] == 'redis']
    qdrant_sorted = sorted(
        [r for r in all_results if r['source'] == 'qdrant'],
        key=lambda x: x.get('score', 0),
        reverse=True
    )
    
    # Display Redis results first
    if redis_sorted:
        print("🔴 FROM REDIS (Recent Buffer):\n")
        for i, result in enumerate(redis_sorted, 1):
            print(format_result(result, i))
            print()
    
    # Then Qdrant results
    if qdrant_sorted:
        print("🔵 FROM QDRANT (Long-term Memory):\n")
        for i, result in enumerate(qdrant_sorted, len(redis_sorted) + 1):
            print(format_result(result, i))
            print()
    
    print(f"=== {len(all_results)} results ===")
    if redis_sorted:
        print(f"  🔴 Redis: {len(redis_sorted)} (exact, recent)")
    if qdrant_sorted:
        print(f"  🔵 Qdrant: {len(qdrant_sorted)} (semantic, long-term)")

if __name__ == "__main__":
    main()
