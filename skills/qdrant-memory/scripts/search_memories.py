#!/usr/bin/env python3
"""
Search memories by semantic similarity in Qdrant
Usage: search_memories.py "Query text" [--limit 5] [--filter-tag tag] [--track-access]

Now with access tracking - updates access_count and last_accessed when memories are retrieved.
"""

import argparse
import json
import sys
import urllib.request
from datetime import datetime

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "kimi_memories"
OLLAMA_URL = "http://localhost:11434/v1"

def get_embedding(text):
    """Generate embedding using snowflake-arctic-embed2 via Ollama"""
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

def update_access_stats(point_id, current_payload):
    """Update access_count and last_accessed for a memory"""
    
    # Get current values or defaults
    access_count = current_payload.get("access_count", 0) + 1
    last_accessed = datetime.now().isoformat()
    
    # Prepare update payload
    update_body = {
        "points": [
            {
                "id": point_id,
                "payload": {
                    "access_count": access_count,
                    "last_accessed": last_accessed
                }
            }
        ]
    }
    
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/payload?wait=true",
        data=json.dumps(update_body).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode())
            return result.get("status") == "ok"
    except Exception as e:
        # Silently fail - don't break search if update fails
        return False

def search_memories(query_vector, limit=5, tag_filter=None, track_access=True):
    """Search memories in Qdrant with optional access tracking"""
    
    search_body = {
        "vector": query_vector,
        "limit": limit,
        "with_payload": True,
        "with_vector": False
    }
    
    # Add filter if tag specified
    if tag_filter:
        search_body["filter"] = {
            "must": [
                {
                    "key": "tags",
                    "match": {
                        "value": tag_filter
                    }
                }
            ]
        }
    
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/search",
        data=json.dumps(search_body).encode(),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            results = result.get("result", [])
            
            # Track access for retrieved memories
            if track_access and results:
                for r in results:
                    point_id = r.get("id")
                    payload = r.get("payload", {})
                    if point_id:
                        update_access_stats(point_id, payload)
            
            return results
    except Exception as e:
        print(f"Error searching memories: {e}", file=sys.stderr)
        return []

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search memories by semantic similarity")
    parser.add_argument("query", help="Search query text")
    parser.add_argument("--limit", type=int, default=5, help="Number of results (default: 5)")
    parser.add_argument("--filter-tag", help="Filter by tag")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-track", action="store_true", help="Don't update access stats")
    
    args = parser.parse_args()
    
    print(f"Generating query embedding...", file=sys.stderr)
    query_vector = get_embedding(args.query)
    
    if query_vector is None:
        print("❌ Failed to generate embedding", file=sys.stderr)
        sys.exit(1)
    
    print(f"Searching Qdrant...", file=sys.stderr)
    results = search_memories(query_vector, args.limit, args.filter_tag, track_access=not args.no_track)
    
    if not results:
        print("No matching memories found.")
        sys.exit(0)
    
    if args.json:
        # JSON output with all metadata
        output = []
        for r in results:
            payload = r["payload"]
            output.append({
                "id": r.get("id"),
                "score": r["score"],
                "text": payload.get("text", ""),
                "date": payload.get("date", ""),
                "tags": payload.get("tags", []),
                "importance": payload.get("importance", "medium"),
                "confidence": payload.get("confidence", "medium"),
                "verified": payload.get("verified", False),
                "source_type": payload.get("source_type", "inferred"),
                "access_count": payload.get("access_count", 0),
                "last_accessed": payload.get("last_accessed", ""),
                "expires_at": payload.get("expires_at", None)
            })
        print(json.dumps(output, indent=2))
    else:
        # Human-readable output
        print(f"\n🔍 Found {len(results)} similar memories:\n")
        for i, r in enumerate(results, 1):
            payload = r["payload"]
            score = r["score"]
            text = payload.get("text", "")[:200]
            if len(payload.get("text", "")) > 200:
                text += "..."
            date = payload.get("date", "unknown")
            tags = ", ".join(payload.get("tags", []))
            importance = payload.get("importance", "medium")
            access_count = payload.get("access_count", 0)
            verified = "✓" if payload.get("verified", False) else "?"
            
            print(f"{i}. [{date}] (score: {score:.3f}) [{importance}] {verified}")
            print(f"   {text}")
            if tags:
                print(f"   Tags: {tags}")
            if access_count > 0:
                print(f"   Accessed: {access_count} times")
            print()
