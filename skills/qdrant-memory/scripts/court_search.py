#!/usr/bin/env python3
"""
Search private_court_docs collection - Manual only

Usage:
    python3 court_search.py "motion to dismiss"
    python3 court_search.py "deposition" --doc-type "discovery"
    python3 court_search.py "case strategy" --case "Smith v. Jones"
"""

import json
import sys
import urllib.request

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION = "private_court_docs"
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

def search_court_docs(query, doc_type=None, case_name=None, limit=5):
    """Search court documents"""
    
    embedding = get_embedding(query)
    if embedding is None:
        return None
    
    # Build filter
    must_clauses = []
    if doc_type:
        must_clauses.append({"key": "doc_type", "match": {"value": doc_type}})
    if case_name:
        must_clauses.append({"key": "case_name", "match": {"value": case_name}})
    
    filter_clause = {"must": must_clauses} if must_clauses else None
    
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
        print(f"Error searching court docs: {e}", file=sys.stderr)
        return None

def format_result(point, idx):
    """Format a search result for display"""
    payload = point.get("payload", {})
    score = point.get("score", 0)
    
    output = f"\n[{idx}] {payload.get('title', 'Untitled')} (score: {score:.3f})\n"
    output += f"    Type: {payload.get('doc_type', 'unknown')}\n"
    
    if payload.get('case_name'):
        output += f"    Case: {payload['case_name']}\n"
    if payload.get('date_filed'):
        output += f"    Filed: {payload['date_filed']}\n"
    
    text = payload.get('text', '')[:400]
    if len(payload.get('text', '')) > 400:
        text += "..."
    output += f"    Content: {text}\n"
    
    return output

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Search private_court_docs")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--doc-type", default=None, 
                       choices=["motion", "brief", "order", "discovery", "correspondence", "notes", "other"],
                       help="Filter by document type")
    parser.add_argument("--case", default=None, help="Filter by case name")
    parser.add_argument("--limit", type=int, default=5, help="Number of results")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    print(f"🔍 Searching private_court_docs: {args.query}")
    filters = []
    if args.doc_type:
        filters.append(f"type={args.doc_type}")
    if args.case:
        filters.append(f"case={args.case}")
    if filters:
        print(f"   Filters: {', '.join(filters)}")
    print()
    
    results = search_court_docs(args.query, args.doc_type, args.case, args.limit)
    
    if results is None:
        print("❌ Search failed", file=sys.stderr)
        sys.exit(1)
    
    if not results:
        print("No results found in private_court_docs")
        return
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"Found {len(results)} results:\n")
        for i, point in enumerate(results, 1):
            print(format_result(point, i))

if __name__ == "__main__":
    main()
