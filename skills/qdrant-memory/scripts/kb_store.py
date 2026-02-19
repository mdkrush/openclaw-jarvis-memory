#!/usr/bin/env python3
"""
Store content to kimi_kb (Knowledge Base) - Manual only with batch support

Usage:
    Single entry:
        python3 kb_store.py "Content text" --title "Title" --domain "Category" --tags "tag1,tag2"
        python3 kb_store.py "Content" --title "X" --url "https://example.com" --source "docs.site"
    
    Batch mode:
        python3 kb_store.py --batch-file entries.json --batch-size 100

Features:
    - Single or batch upload
    - Duplicate detection by title/URL
    - Domain categorization
    - Access tracking
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION = "kimi_kb"
OLLAMA_URL = "http://localhost:11434/v1"
DEFAULT_BATCH_SIZE = 100


def check_existing(title: str = None, url: str = None) -> tuple:
    """Check if entry already exists by title or URL"""
    try:
        # Check by URL first if provided
        if url:
            scroll_data = json.dumps({
                "limit": 10,
                "with_payload": True,
                "filter": {"must": [{"key": "url", "match": {"value": url}}]}
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
                    return points[0]["id"], "url"
        
        # Check by title
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
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode())
            return result["data"][0]["embedding"]
    except Exception as e:
        print(f"Error generating embedding: {e}", file=sys.stderr)
        return None


def batch_upload_embeddings(texts: List[str]) -> List[Optional[List[float]]]:
    """Generate embeddings for multiple texts in batch"""
    if not texts:
        return []
    
    data = json.dumps({
        "model": "snowflake-arctic-embed2",
        "input": [t[:8192] for t in texts]
    }).encode()
    
    req = urllib.request.Request(
        f"{OLLAMA_URL}/embeddings",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode())
            return [d["embedding"] for d in result["data"]]
    except Exception as e:
        print(f"Error generating batch embeddings: {e}", file=sys.stderr)
        return [None] * len(texts)


def upload_points_batch(points: List[Dict[str, Any]], batch_size: int = DEFAULT_BATCH_SIZE) -> tuple:
    """Upload points in batches to Qdrant"""
    total = len(points)
    uploaded = 0
    failed = 0
    
    for i in range(0, total, batch_size):
        batch = points[i:i + batch_size]
        
        upsert_data = {"points": batch}
        
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true",
            data=json.dumps(upsert_data).encode(),
            headers={"Content-Type": "application/json"},
            method="PUT"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode())
                if result.get("status") == "ok":
                    uploaded += len(batch)
                    print(f"  ✅ Uploaded batch {i//batch_size + 1}: {len(batch)} points")
                else:
                    print(f"  ❌ Batch {i//batch_size + 1} failed: {result}")
                    failed += len(batch)
        except Exception as e:
            print(f"  ❌ Batch {i//batch_size + 1} error: {e}", file=sys.stderr)
            failed += len(batch)
    
    return uploaded, failed


def store_single(
    text: str,
    embedding: List[float],
    title: str = None,
    url: str = None,
    source: str = None,
    domain: str = "general",
    tags: List[str] = None,
    content_type: str = "document",
    replace: bool = False
) -> bool:
    """Store single KB entry"""
    
    # Check for existing entry
    existing_id, match_type = check_existing(title=title, url=url)
    if existing_id:
        if not replace:
            print(f"⚠️  Entry '{title}' already exists (matched by {match_type}, ID: {existing_id})")
            print(f"   Use --replace to overwrite")
            return False
    
    point_id = existing_id if existing_id else str(uuid.uuid4())
    
    payload = {
        "text": text,
        "title": title or "Untitled",
        "url": url or "",
        "source": source or "manual",
        "domain": domain or "general",
        "tags": tags or [],
        "content_type": content_type,
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
        print(f"Error storing to KB: {e}", file=sys.stderr)
        return False


def store_batch(
    entries: List[Dict[str, Any]],
    batch_size: int = DEFAULT_BATCH_SIZE,
    check_duplicates: bool = True
) -> tuple:
    """Store multiple KB entries in batch with optional duplicate checking"""
    if not entries:
        return 0, 0
    
    print(f"Processing {len(entries)} entries...")
    
    # Filter duplicates if requested
    entries_to_process = []
    duplicates = 0
    
    if check_duplicates:
        for entry in entries:
            existing_id, match_type = check_existing(
                title=entry.get("title"),
                url=entry.get("url")
            )
            if existing_id:
                print(f"  ⏭️  Skipping duplicate: {entry.get('title', 'Untitled')} ({match_type})")
                duplicates += 1
            else:
                entries_to_process.append(entry)
    else:
        entries_to_process = entries
    
    if not entries_to_process:
        print(f"All {len(entries)} entries already exist")
        return 0, 0
    
    print(f"Generating embeddings for {len(entries_to_process)} entries...")
    texts = [e["content"] for e in entries_to_process]
    embeddings = batch_upload_embeddings(texts)
    
    # Prepare points
    points = []
    failed_embeddings = 0
    
    for entry, embedding in zip(entries_to_process, embeddings):
        if embedding is None:
            failed_embeddings += 1
            continue
        
        point_id = str(uuid.uuid4())
        
        payload = {
            "text": entry["content"],
            "title": entry.get("title", "Untitled"),
            "url": entry.get("url", ""),
            "source": entry.get("source", "manual"),
            "domain": entry.get("domain", "general"),
            "tags": entry.get("tags", []),
            "content_type": entry.get("type", "document"),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "created_at": datetime.now().isoformat(),
            "access_count": 0
        }
        
        points.append({
            "id": point_id,
            "vector": embedding,
            "payload": payload
        })
    
    if not points:
        return 0, failed_embeddings + duplicates
    
    # Upload in batches
    print(f"Uploading {len(points)} entries in batches of {batch_size}...")
    uploaded, failed_upload = upload_points_batch(points, batch_size)
    
    return uploaded, failed_embeddings + failed_upload + duplicates


def main():
    parser = argparse.ArgumentParser(description="Store content to kimi_kb")
    parser.add_argument("content", nargs="?", help="Content to store")
    parser.add_argument("--title", default=None, help="Title of the content")
    parser.add_argument("--url", default=None, help="Source URL if from web")
    parser.add_argument("--source", default=None, help="Source name")
    parser.add_argument("--domain", default="general", help="Domain/category")
    parser.add_argument("--tags", default=None, help="Comma-separated tags")
    parser.add_argument("--type", default="document", choices=["document", "web", "code", "note"],
                       help="Content type")
    parser.add_argument("--replace", action="store_true", help="Replace existing entry")
    parser.add_argument("--batch-file", help="JSON file with multiple entries")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help=f"Batch size")
    parser.add_argument("--no-check-duplicates", action="store_true", help="Skip duplicate checking in batch mode")
    
    args = parser.parse_args()
    
    # Batch mode
    if args.batch_file:
        print(f"Batch mode: Loading entries from {args.batch_file}")
        try:
            with open(args.batch_file, 'r') as f:
                entries = json.load(f)
            
            if not isinstance(entries, list):
                print("Batch file must contain a JSON array", file=sys.stderr)
                sys.exit(1)
            
            print(f"Loaded {len(entries)} entries")
            uploaded, failed = store_batch(
                entries,
                args.batch_size,
                check_duplicates=not args.no_check_duplicates
            )
            
            print(f"\n{'=' * 50}")
            print(f"Batch complete: {uploaded} uploaded, {failed} failed")
            sys.exit(0 if failed == 0 else 1)
            
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Single entry mode
    if not args.content:
        print("Error: Provide content or use --batch-file", file=sys.stderr)
        parser.print_help()
        sys.exit(1)
    
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
    
    print(f"Generating embedding...")
    embedding = get_embedding(args.content)
    
    if embedding is None:
        print("❌ Failed to generate embedding")
        sys.exit(1)
    
    print(f"Storing to kimi_kb: {args.title or 'Untitled'}...")
    
    if store_single(
        text=args.content,
        embedding=embedding,
        title=args.title,
        url=args.url,
        source=args.source,
        domain=args.domain,
        tags=tags,
        content_type=args.type,
        replace=args.replace
    ):
        print(f"✅ Stored to kimi_kb ({args.domain})")
    else:
        print("❌ Failed to store")
        sys.exit(1)


if __name__ == "__main__":
    main()
