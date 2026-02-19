#!/usr/bin/env python3
"""
Search kimi_kb (Knowledge Base) - Manual only

Usage:
    python3 kb_search.py "query"
    python3 kb_search.py "docker volumes" --domain "Docker"
    python3 kb_search.py "query" --include-urls
"""

import json
import sys
import urllib.request
from pathlib import Path

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION = "kimi_kb"
OLLAMA_URL = "http://localhost:11434/v1"

def get_embedding(text):
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
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode())
            return result["data"][0]["embedding"]
    except Exception as e:
        print(f"Error generating embedding: {e}", file=sys.stderr)
        return None

def search_kb(query, domain=None, limit=5):
    """Search knowledge base"""
    
    embedding = get_embedding(query)
    if embedding is None:
        return None
    
    # Build filter if domain specified
    filter_clause = {}
    if domain:
        filter_clause = {
            "must": [
                {"key": "domain", "match": {"value": domain}}
            ]
        }
    
    search_body = {
        "vector": embedding,
        "limit": limit,
        "with_payload": True,
        "with_vector": False
    }
    
    if filter_clause:
        search_body["filter"] = filter_clause
    
    data = json.dumps(search_body).encode()
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            return result.get("result", [])
    except Exception as e:
        print(f"Error searching KB: {e}", file=sys.stderr)
        return None

def format_result(point, idx):
    """Format a search result for display"""
    payload = point.get("payload", {})
    score = point.get("score", 0)
    
    output = f"\n[{idx}] {payload.get('title', 'Untitled')} (score: {score:.3f})\n"
    output += f"    Domain: {payload.get('domain', 'unknown')}\n"
    
    if payload.get('url'):
        output += f"    URL: {payload['url']}\n"
    if payload.get('source'):
        output += f"    Source: {payload['source']}\n"
    
    text = payload.get('text', '')[:300]
    if len(payload.get('text', '')) > 300:
        text += "..."
    output += f"    Content: {text}\n"
    
    return output

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Search kimi_kb")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--domain", default=None, help="Filter by domain")
    parser.add_argument("--limit", type=int, default=5, help="Number of results")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    print(f"🔍 Searching kimi_kb: {args.query}")
    if args.domain:
        print(f"   Filter: domain={args.domain}")
    print()
    
    results = search_kb(args.query, args.domain, args.limit)
    
    if results is None:
        print("❌ Search failed", file=sys.stderr)
        sys.exit(1)
    
    if not results:
        print("No results found in kimi_kb")
        return
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"Found {len(results)} results:\n")
        for i, point in enumerate(results, 1):
            print(format_result(point, i))

if __name__ == "__main__":
    main()
