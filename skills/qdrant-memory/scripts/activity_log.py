#!/usr/bin/env python3
"""
Shared Activity Log for Kimi and Max
Prevents duplicate work by logging actions to Qdrant
"""

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "activity_log"
VECTOR_SIZE = 768  # nomic-embed-text

# Embedding function (simple keyword-based for now, or use nomic)
def simple_embed(text: str) -> list[float]:
    """Simple hash-based embedding for semantic similarity"""
    # In production, use nomic-embed-text via API
    # For now, use a simple approach that groups similar texts
    words = text.lower().split()
    vector = [0.0] * VECTOR_SIZE
    for i, word in enumerate(words[:100]):  # Limit to first 100 words
        h = hash(word) % VECTOR_SIZE
        vector[h] += 1.0
    # Normalize
    norm = sum(x*x for x in vector) ** 0.5
    if norm > 0:
        vector = [x/norm for x in vector]
    return vector

def init_collection(client: QdrantClient):
    """Create activity_log collection if not exists"""
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
        )
        print(f"Created collection: {COLLECTION_NAME}")

def log_activity(
    agent: str,
    action_type: str,
    description: str,
    affected_files: Optional[list] = None,
    status: str = "completed",
    metadata: Optional[dict] = None
) -> str:
    """
    Log an activity to the shared activity log
    
    Args:
        agent: "Kimi" or "Max"
        action_type: e.g., "cron_created", "file_edited", "config_changed", "task_completed"
        description: Human-readable description of what was done
        affected_files: List of file paths or systems affected
        status: "completed", "in_progress", "blocked", "failed"
        metadata: Additional key-value pairs
    
    Returns:
        activity_id (UUID)
    """
    client = QdrantClient(url=QDRANT_URL)
    init_collection(client)
    
    activity_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # Build searchable text
    searchable_text = f"{agent} {action_type} {description} {' '.join(affected_files or [])}"
    vector = simple_embed(searchable_text)
    
    payload = {
        "agent": agent,
        "action_type": action_type,
        "description": description,
        "affected_files": affected_files or [],
        "status": status,
        "timestamp": timestamp,
        "date": date_str,
        "activity_id": activity_id,
        "metadata": metadata or {}
    }
    
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[PointStruct(id=activity_id, vector=vector, payload=payload)]
    )
    
    return activity_id

def get_recent_activities(
    agent: Optional[str] = None,
    action_type: Optional[str] = None,
    hours: int = 24,
    limit: int = 50
) -> list[dict]:
    """
    Query recent activities
    
    Args:
        agent: Filter by agent name ("Kimi" or "Max") or None for both
        action_type: Filter by action type or None for all
        hours: Look back this many hours
        limit: Max results
    """
    client = QdrantClient(url=QDRANT_URL)
    
    # Get all points and filter client-side (Qdrant payload filtering can be tricky)
    # For small collections, this is fine. For large ones, use scroll with filter
    all_points = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=1000  # Get recent batch
    )[0]
    
    results = []
    cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
    
    for point in all_points:
        payload = point.payload
        ts = payload.get("timestamp", "")
        try:
            point_time = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except:
            continue
        
        if point_time < cutoff:
            continue
        
        if agent and payload.get("agent") != agent:
            continue
        
        if action_type and payload.get("action_type") != action_type:
            continue
        
        results.append(payload)
    
    # Sort by timestamp descending
    results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return results[:limit]

def search_activities(query: str, limit: int = 10) -> list[dict]:
    """Semantic search across activity descriptions"""
    client = QdrantClient(url=QDRANT_URL)
    vector = simple_embed(query)
    
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        limit=limit
    )
    
    return [r.payload for r in results]

def check_for_duplicates(action_type: str, description_keywords: str, hours: int = 6) -> bool:
    """
    Check if similar work was recently done
    Returns True if duplicate detected, False otherwise
    """
    recent = get_recent_activities(action_type=action_type, hours=hours)
    
    keywords = description_keywords.lower().split()
    for activity in recent:
        desc = activity.get("description", "").lower()
        if all(kw in desc for kw in keywords):
            print(f"⚠️  Duplicate detected: {activity['agent']} did similar work {activity['timestamp']}")
            print(f"   Description: {activity['description']}")
            return True
    
    return False

def main():
    parser = argparse.ArgumentParser(description="Shared Activity Log for Kimi/Max")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Log command
    log_parser = subparsers.add_parser("log", help="Log an activity")
    log_parser.add_argument("--agent", required=True, choices=["Kimi", "Max"], help="Which agent performed the action")
    log_parser.add_argument("--action", required=True, help="Action type (e.g., cron_created, file_edited)")
    log_parser.add_argument("--description", required=True, help="What was done")
    log_parser.add_argument("--files", nargs="*", help="Files/systems affected")
    log_parser.add_argument("--status", default="completed", choices=["completed", "in_progress", "blocked", "failed"])
    log_parser.add_argument("--check-duplicate", action="store_true", help="Check for duplicates before logging")
    log_parser.add_argument("--duplicate-keywords", help="Keywords to check for duplicates (if different from description)")
    
    # Recent command
    recent_parser = subparsers.add_parser("recent", help="Show recent activities")
    recent_parser.add_argument("--agent", choices=["Kimi", "Max"], help="Filter by agent")
    recent_parser.add_argument("--action", help="Filter by action type")
    recent_parser.add_argument("--hours", type=int, default=24, help="Hours to look back")
    recent_parser.add_argument("--limit", type=int, default=20, help="Max results")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search activities")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=10)
    
    # Check command
    check_parser = subparsers.add_parser("check", help="Check for duplicate work")
    check_parser.add_argument("--action", required=True, help="Action type")
    check_parser.add_argument("--keywords", required=True, help="Keywords to check")
    check_parser.add_argument("--hours", type=int, default=6, help="Hours to look back")
    
    args = parser.parse_args()
    
    if args.command == "log":
        if args.check_duplicate:
            keywords = args.duplicate_keywords or args.description
            if check_for_duplicates(args.action, keywords):
                response = input("Proceed anyway? (y/n): ")
                if response.lower() != "y":
                    print("Cancelled.")
                    sys.exit(0)
        
        activity_id = log_activity(
            agent=args.agent,
            action_type=args.action,
            description=args.description,
            affected_files=args.files,
            status=args.status
        )
        print(f"✓ Logged activity: {activity_id}")
        
    elif args.command == "recent":
        activities = get_recent_activities(
            agent=args.agent,
            action_type=args.action,
            hours=args.hours,
            limit=args.limit
        )
        
        print(f"\nRecent activities (last {args.hours}h):\n")
        for a in activities:
            agent_icon = "🤖" if a["agent"] == "Max" else "🎙️"
            status_icon = {
                "completed": "✓",
                "in_progress": "◐",
                "blocked": "✗",
                "failed": "⚠"
            }.get(a["status"], "?")
            
            print(f"{agent_icon} [{a['timestamp'][:19]}] {status_icon} {a['action_type']}")
            print(f"   {a['description']}")
            if a['affected_files']:
                print(f"   Files: {', '.join(a['affected_files'])}")
            print()
            
    elif args.command == "search":
        results = search_activities(args.query, args.limit)
        
        print(f"\nSearch results for '{args.query}':\n")
        for r in results:
            print(f"[{r['agent']}] {r['action_type']}: {r['description']}")
            print(f"   {r['timestamp'][:19]} | Status: {r['status']}")
            print()
            
    elif args.command == "check":
        is_dup = check_for_duplicates(args.action, args.keywords, args.hours)
        sys.exit(1 if is_dup else 0)
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
