#!/usr/bin/env python3
"""
Store content to private_court_docs collection - Manual only
For court documents and legal discussions

Usage:
    python3 court_store.py "Content text" --title "Document Title" --doc-type "Motion" --date-filed "2026-01-15"
    python3 court_store.py "Discussion about case strategy" --title "Case Strategy Notes" --doc-type "notes"
"""

import json
import sys
import urllib.request
import uuid
from datetime import datetime

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION = "private_court_docs"
OLLAMA_URL = "http://localhost:11434/v1"

def check_existing(title=None, case_name=None, date_filed=None):
    """Check if entry already exists"""
    try:
        if title:
            scroll_data = json.dumps({
                "limit": 10,
                "with_payload": True,
                "filter": {"must": [{"key": "title", "match": {"value": title}}]}
            }).encode()
            req = urllib.request.Request(
                f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll",
                data=scroll_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
                points = result.get("result", {}).get("points", [])
                if points:
                    return points[0]["id"], "title"
    except Exception as e:
        print(f"Warning: Could not check existing: {e}", file=sys.stderr)
    return None, None

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

def store_to_court(text, title=None, doc_type=None, date_filed=None, 
                   case_name=None, tags=None, replace=False):
    """Store content to private_court_docs collection"""
    
    embedding = get_embedding(text)
    if embedding is None:
        return False
    
    # Check for existing entry
    existing_id, match_type = check_existing(title=title)
    if existing_id:
        if not replace:
            print(f"⚠️  Entry '{title}' already exists (matched by {match_type}, ID: {existing_id})")
            print(f"   Use --replace to overwrite")
            return False
    
    point_id = existing_id if existing_id else str(uuid.uuid4())
    
    payload = {
        "text": text,
        "title": title or "Untitled",
        "doc_type": doc_type or "document",
        "date_filed": date_filed or datetime.now().strftime("%Y-%m-%d"),
        "case_name": case_name or "",
        "tags": tags or [],
        "date": datetime.now().strftime("%Y-%m-%d"),
        "created_at": datetime.now().isoformat(),
        "access_count": 0
    }
    
    point = {
        "points": [{
            "id": point_id,
            "vector": embedding,
            "payload": payload
        }]
    }
    
    data = json.dumps(point).encode()
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true",
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            return result.get("status") == "ok"
    except Exception as e:
        print(f"Error storing to court docs: {e}", file=sys.stderr)
        return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Store content to private_court_docs")
    parser.add_argument("content", help="Content to store")
    parser.add_argument("--title", default=None, help="Title of the document")
    parser.add_argument("--doc-type", default="document", 
                       choices=["motion", "brief", "order", "discovery", "correspondence", "notes", "other"],
                       help="Type of document")
    parser.add_argument("--date-filed", default=None, help="Date filed (YYYY-MM-DD)")
    parser.add_argument("--case", default=None, help="Case name/number")
    parser.add_argument("--tags", default=None, help="Comma-separated tags")
    parser.add_argument("--replace", action="store_true", help="Replace existing entry with same title")
    
    args = parser.parse_args()
    
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
    
    print(f"Storing to private_court_docs: {args.title or 'Untitled'}...")
    
    if store_to_court(
        text=args.content,
        title=args.title,
        doc_type=args.doc_type,
        date_filed=args.date_filed,
        case_name=args.case,
        tags=tags,
        replace=args.replace
    ):
        print(f"✅ Stored to private_court_docs ({args.doc_type})")
    else:
        print("❌ Failed to store")
        sys.exit(1)

if __name__ == "__main__":
    main()
