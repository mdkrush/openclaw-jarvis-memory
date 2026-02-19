#!/usr/bin/env python3
"""
Enhanced memory storage with metadata support and batch upload capability
Usage: store_memory.py "Memory text" [--tags tag1,tag2] [--importance medium] 
                         [--confidence high] [--source user|inferred|external]
                         [--verified] [--expires 2026-03-01] [--related id1,id2]
                         [--batch-mode] [--batch-size N]

Features:
    - Single or batch memory storage
    - Duplicate detection with --replace flag
    - Enhanced metadata (importance, confidence, source_type, etc.)
    - Access tracking (access_count, last_accessed)
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "kimi_memories"
OLLAMA_URL = "http://localhost:11434/v1"
DEFAULT_BATCH_SIZE = 100


def check_existing(date: str = None) -> Optional[str]:
    """Check if entry already exists for this date"""
    if not date:
        return None
    
    try:
        scroll_data = json.dumps({
            "limit": 100,
            "with_payload": True,
            "filter": {
                "must": [{"key": "date", "match": {"value": date}}]
            }
        }).encode()
        
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
            data=scroll_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            points = result.get("result", {}).get("points", [])
            if points:
                return points[0]["id"]  # Return existing ID
    except Exception as e:
        print(f"Warning: Could not check existing: {e}", file=sys.stderr)
    return None


def get_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding using snowflake-arctic-embed2 via Ollama"""
    data = json.dumps({
        "model": "snowflake-arctic-embed2",
        "input": text[:8192]  # Limit to 8k chars
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


def batch_upload_embeddings(texts: List[str]) -> List[Optional[List[float]]]:
    """Generate embeddings for multiple texts in one batch"""
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
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points?wait=true",
            data=json.dumps(upsert_data).encode(),
            headers={"Content-Type": "application/json"},
            method="PUT"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode())
                if result.get("status") == "ok":
                    uploaded += len(batch)
                else:
                    print(f"Batch upload failed: {result}", file=sys.stderr)
                    failed += len(batch)
        except Exception as e:
            print(f"Batch upload error: {e}", file=sys.stderr)
            failed += len(batch)
    
    return uploaded, failed


def store_single_memory(
    text: str,
    embedding: List[float],
    tags: List[str] = None,
    importance: str = "medium",
    date: str = None,
    source: str = "conversation",
    confidence: str = "high",
    source_type: str = "user",
    verified: bool = True,
    expires_at: str = None,
    related_memories: List[str] = None,
    replace: bool = False
) -> Optional[str]:
    """Store a single memory in Qdrant with enhanced metadata"""
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # Check for existing entry on same date
    existing_id = check_existing(date=date) if date else None
    if existing_id and not replace:
        print(f"⚠️  Entry for {date} already exists (ID: {existing_id})")
        print(f"   Use --replace to overwrite")
        return None
    
    # Use existing ID if replacing, otherwise generate new
    point_id = existing_id if existing_id else str(uuid.uuid4())
    
    # Build payload with all metadata
    payload = {
        "text": text,
        "date": date,
        "tags": tags or [],
        "importance": importance,
        "source": source,
        "confidence": confidence,
        "source_type": source_type,
        "verified": verified,
        "created_at": datetime.now().isoformat(),
        "access_count": 0,
        "last_accessed": datetime.now().isoformat()
    }
    
    # Optional metadata
    if expires_at:
        payload["expires_at"] = expires_at
    if related_memories:
        payload["related_memories"] = related_memories
    
    # Qdrant upsert format
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
            else:
                print(f"Qdrant response: {result}", file=sys.stderr)
                return None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"HTTP Error {e.code}: {error_body}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error storing memory: {e}", file=sys.stderr)
        return None


def store_memories_batch(
    memories: List[Dict[str, Any]],
    batch_size: int = DEFAULT_BATCH_SIZE
) -> tuple:
    """Store multiple memories in batch"""
    if not memories:
        return 0, 0
    
    # Generate embeddings for all
    texts = [m["text"] for m in memories]
    print(f"Generating embeddings for {len(texts)} memories...")
    embeddings = batch_upload_embeddings(texts)
    
    # Prepare points
    points = []
    failed_indices = []
    
    for i, (memory, embedding) in enumerate(zip(memories, embeddings)):
        if embedding is None:
            failed_indices.append(i)
            continue
        
        point_id = str(uuid.uuid4())
        date = memory.get("date", datetime.now().strftime("%Y-%m-%d"))
        
        payload = {
            "text": memory["text"],
            "date": date,
            "tags": memory.get("tags", []),
            "importance": memory.get("importance", "medium"),
            "source": memory.get("source", "conversation"),
            "confidence": memory.get("confidence", "high"),
            "source_type": memory.get("source_type", "user"),
            "verified": memory.get("verified", True),
            "created_at": datetime.now().isoformat(),
            "access_count": 0,
            "last_accessed": datetime.now().isoformat()
        }
        
        # NOTE: User requested NO memory expiration - permanent retention
        # expires_at is accepted for API compatibility but ignored
        if memory.get("expires_at"):
            payload["expires_at"] = memory["expires_at"]
        if memory.get("related_memories"):
            payload["related_memories"] = memory["related_memories"]
        
        points.append({
            "id": point_id,
            "vector": embedding,
            "payload": payload
        })
    
    if not points:
        return 0, len(memories)
    
    # Upload in batches
    print(f"Uploading {len(points)} memories in batches of {batch_size}...")
    uploaded, failed_upload = upload_points_batch(points, batch_size)
    
    return uploaded, len(failed_indices) + failed_upload


def parse_date(date_str: str) -> Optional[str]:
    """Validate date format"""
    if not date_str:
        return None
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        print(f"Invalid date format: {date_str}. Use YYYY-MM-DD.", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Store memories in Qdrant with metadata")
    parser.add_argument("text", nargs="?", help="Memory text to store")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--importance", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--date", help="Date in YYYY-MM-DD format")
    parser.add_argument("--source", default="conversation", help="Source of the memory")
    parser.add_argument("--confidence", default="high", choices=["high", "medium", "low"])
    parser.add_argument("--source-type", default="user", choices=["user", "inferred", "external"])
    parser.add_argument("--verified", action="store_true", default=True)
    parser.add_argument("--expires", help="Expiration date YYYY-MM-DD (NOTE: User prefers permanent retention)")
    parser.add_argument("--related", help="Comma-separated related memory IDs")
    parser.add_argument("--replace", action="store_true", help="Replace existing entry for the same date")
    parser.add_argument("--batch-file", help="JSON file with multiple memories for batch upload")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help=f"Batch size (default: {DEFAULT_BATCH_SIZE})")
    
    args = parser.parse_args()
    
    # Batch mode
    if args.batch_file:
        print(f"Batch mode: Loading memories from {args.batch_file}")
        try:
            with open(args.batch_file, 'r') as f:
                memories = json.load(f)
            
            if not isinstance(memories, list):
                print("Batch file must contain a JSON array of memories", file=sys.stderr)
                sys.exit(1)
            
            print(f"Loaded {len(memories)} memories for batch upload")
            uploaded, failed = store_memories_batch(memories, args.batch_size)
            
            print(f"\n{'=' * 50}")
            print(f"Batch upload complete:")
            print(f"  Uploaded: {uploaded}")
            print(f"  Failed: {failed}")
            
            sys.exit(0 if failed == 0 else 1)
            
        except Exception as e:
            print(f"Error loading batch file: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Single memory mode
    if not args.text:
        print("Error: Either provide text argument or use --batch-file", file=sys.stderr)
        parser.print_help()
        sys.exit(1)
    
    # Parse tags and related memories
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
    related = [r.strip() for r in args.related.split(",")] if args.related else None
    
    # Validate date
    date = parse_date(args.date)
    if args.date and not date:
        sys.exit(1)
    
    print(f"Generating embedding...")
    embedding = get_embedding(args.text)
    
    if embedding is None:
        print("❌ Failed to generate embedding", file=sys.stderr)
        sys.exit(1)
    
    print(f"Storing memory (vector dim: {len(embedding)})...")
    point_id = store_single_memory(
        text=args.text,
        embedding=embedding,
        tags=tags,
        importance=args.importance,
        date=date,
        source=args.source,
        confidence=args.confidence,
        source_type=args.source_type,
        verified=args.verified,
        expires_at=args.expires,
        related_memories=related,
        replace=args.replace
    )
    
    if point_id:
        print(f"✅ Memory stored successfully")
        print(f"   ID: {point_id}")
        print(f"   Tags: {tags}")
        print(f"   Importance: {args.importance}")
        print(f"   Confidence: {args.confidence}")
        print(f"   Source: {args.source_type}")
        if args.expires:
            print(f"   Expires: {args.expires}")
    else:
        print(f"❌ Failed to store memory", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
