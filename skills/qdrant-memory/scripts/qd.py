#!/usr/bin/env python3
"""
Qdrant_Documents - Complete management script
Usage: qd.py <command> [options]

Commands:
    list        - List collection info and stats
    search      - Search documents
    store       - Store new document
    delete      - Delete document by ID
    export      - Export all documents to JSON
    import      - Import documents from JSON
    count       - Get total document count
    tags        - List unique tags
"""

import argparse
import json
import sys
import urllib.request
import uuid
from datetime import datetime

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION = "Qdrant_Documents"
OLLAMA_URL = "http://localhost:11434/v1"

# ============================================================================
# UTILITIES
# ============================================================================

def get_embedding(text, model="nomic-embed-text"):
    """Generate embedding using Ollama"""
    data = json.dumps({"model": model, "input": text[:8000]}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/embeddings",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())["data"][0]["embedding"]
    except Exception as e:
        print(f"Embedding error: {e}", file=sys.stderr)
        return None

def make_request(url, data=None, method="GET"):
    """Make HTTP request"""
    req = urllib.request.Request(url, method=method)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    return req

def check_collection():
    """Verify collection exists"""
    try:
        req = make_request(f"{QDRANT_URL}/collections/{COLLECTION}")
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.read()
    except:
        return None

# ============================================================================
# COMMANDS
# ============================================================================

def cmd_list(args):
    """List collection info"""
    data = check_collection()
    if not data:
        print(f"❌ Collection '{COLLECTION}' not found")
        sys.exit(1)
    
    info = json.loads(data.decode())["result"]
    
    print(f"\n📚 Collection: {COLLECTION}")
    print(f"   Status: {info['status']}")
    print(f"   Points: {info['points_count']:,}")
    print(f"   Vectors: {info['indexed_vectors_count']:,}")
    print(f"   Segments: {info['segments_count']}")
    print(f"   Vector size: {info['config']['params']['vectors']['size']}")
    print(f"   Distance: {info['config']['params']['vectors']['distance']}")
    print(f"   Optimizer: {info['optimizer_status']}")
    print()
    
    # Show payload schema
    print("📋 Payload Schema:")
    for field, schema in info.get("payload_schema", {}).items():
        if isinstance(schema, dict) and "data_type" in schema:
            print(f"   - {field}: {schema['data_type']} ({schema.get('points',0):,} points)")
    print()

def cmd_count(args):
    """Get document count"""
    req = make_request(f"{QDRANT_URL}/collections/{COLLECTION}")
    with urllib.request.urlopen(req, timeout=5) as r:
        count = json.loads(r.read().decode())["result"]["points_count"]
    print(f"{count}")

def cmd_search(args):
    """Search documents"""
    embedding = get_embedding(args.query)
    if not embedding:
        print("❌ Failed to generate embedding")
        sys.exit(1)
    
    search_body = {
        "vector": embedding,
        "limit": args.limit,
        "with_payload": True,
        "with_vector": False
    }
    
    if args.tag:
        search_body["filter"] = {"must": [{"key": "tag", "match": {"value": args.tag}}]}
    
    data = json.dumps(search_body).encode()
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            results = json.loads(r.read().decode())["result"]
    except Exception as e:
        print(f"❌ Search failed: {e}")
        sys.exit(1)
    
    if not results:
        print("No results found")
        return
    
    print(f"Found {len(results)} results:\n")
    for i, r in enumerate(results, 1):
        p = r.get("payload", {})
        print(f"[{i}] Score: {r['score']:.3f}")
        print(f"    Tags: {p.get('tag', 'none')}")
        text = p.get('text', '')[:args.chars]
        if len(p.get('text', '')) > args.chars:
            text += "..."
        print(f"    Text: {text}")
        print()

def cmd_store(args):
    """Store a document"""
    # Read from file or use text argument
    if args.file:
        with open(args.file, 'r') as f:
            text = f.read()
    else:
        text = args.text
    
    if not text:
        print("❌ No text to store")
        sys.exit(1)
    
    embedding = get_embedding(text)
    if not embedding:
        print("❌ Failed to generate embedding")
        sys.exit(1)
    
    # Parse tags
    tags = args.tag.split(",") if args.tag else []
    sections = args.section.split(",") if args.section else []
    
    point = {
        "points": [{
            "id": str(uuid.uuid4()),
            "vector": embedding,
            "payload": {
                "text": text,
                "tag": tags,
                "sections": sections,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "created_at": datetime.now().isoformat()
            }
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
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read().decode())
            if result.get("status") == "ok":
                print(f"✅ Stored document ({len(text)} chars, {len(embedding)}D vector)")
            else:
                print(f"❌ Store failed: {result}")
                sys.exit(1)
    except Exception as e:
        print(f"❌ Store error: {e}")
        sys.exit(1)

def cmd_delete(args):
    """Delete a document by ID"""
    req = make_request(
        f"{QDRANT_URL}/collections/{COLLECTION}/points/{args.id}",
        method="DELETE"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"✅ Deleted point {args.id}")
    except Exception as e:
        print(f"❌ Delete error: {e}")
        sys.exit(1)

def cmd_export(args):
    """Export all documents to JSON"""
    print(f"Exporting {COLLECTION}...", file=sys.stderr)
    
    # Get all points
    all_points = []
    offset = None
    
    while True:
        scroll_body = {"limit": 100, "with_payload": True, "with_vector": False}
        if offset:
            scroll_body["offset"] = offset
        
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll",
            data=json.dumps(scroll_body).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                result = json.loads(r.read().decode())
                points = result.get("result", {}).get("points", [])
                if not points:
                    break
                all_points.extend(points)
                offset = result.get("result", {}).get("next_page_offset")
                if not offset:
                    break
        except Exception as e:
            print(f"❌ Export error: {e}")
            sys.exit(1)
    
    # Format output
    output = []
    for p in all_points:
        output.append({
            "id": p["id"],
            "payload": p.get("payload", {})
        })
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"✅ Exported {len(output)} documents to {args.output}")
    else:
        print(json.dumps(output, indent=2))

def cmd_import(args):
    """Import documents from JSON"""
    with open(args.file, 'r') as f:
        documents = json.load(f)
    
    print(f"Importing {len(documents)} documents...")
    
    success = 0
    for doc in documents:
        text = doc.get("payload", {}).get("text", "")
        if not text:
            continue
        
        embedding = get_embedding(text)
        if not embedding:
            print(f"  ⚠️ Skipping {doc.get('id')}: embedding failed")
            continue
        
        point = {
            "points": [{
                "id": doc.get("id", str(uuid.uuid4())),
                "vector": embedding,
                "payload": doc.get("payload", {})
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
            with urllib.request.urlopen(req, timeout=30) as r:
                if json.loads(r.read().decode()).get("status") == "ok":
                    success += 1
        except:
            pass
    
    print(f"✅ Imported {success}/{len(documents)} documents")

def cmd_tags(args):
    """List unique tags"""
    # Use scroll to get all tags
    all_tags = set()
    offset = None
    
    while True:
        scroll_body = {"limit": 100, "with_payload": True, "with_vector": False}
        if offset:
            scroll_body["offset"] = offset
        
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll",
            data=json.dumps(scroll_body).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                result = json.loads(r.read().decode())
                points = result.get("result", {}).get("points", [])
                if not points:
                    break
                for p in points:
                    tags = p.get("payload", {}).get("tag", [])
                    if isinstance(tags, list):
                        all_tags.update(tags)
                    elif tags:
                        all_tags.add(tags)
                offset = result.get("result", {}).get("next_page_offset")
                if not offset:
                    break
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
    
    print(f"\n🏷️  Unique tags ({len(all_tags)}):")
    for tag in sorted(all_tags):
        print(f"   - {tag}")
    print()

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description=f"Qdrant_Documents management ({COLLECTION})",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  qd.py list                              # Show collection stats
  qd.py search "docker volumes"           # Search documents
  qd.py search "query" --tag kubernetes   # Filter by tag
  qd.py store "text here" --tag "docker"  # Store document
  qd.py store --file README.md --tag "doc"
  qd.py export --output backup.json       # Export all
  qd.py tags                              # List all tags
        """
    )
    
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    
    # list
    subparsers.add_parser("list", help="Show collection info")
    
    # count
    subparsers.add_parser("count", help="Get document count")
    
    # search
    p_search = subparsers.add_parser("search", help="Search documents")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--tag", help="Filter by tag")
    p_search.add_argument("--limit", type=int, default=5)
    p_search.add_argument("--chars", type=int, default=200)
    
    # store
    p_store = subparsers.add_parser("store", help="Store document")
    p_store.add_argument("text", nargs="?", help="Text to store")
    p_store.add_argument("--file", help="Read from file")
    p_store.add_argument("--tag", help="Comma-separated tags")
    p_store.add_argument("--section", help="Comma-separated sections", default="")
    
    # delete
    p_delete = subparsers.add_parser("delete", help="Delete by ID")
    p_delete.add_argument("id", help="Point ID to delete")
    
    # export
    p_export = subparsers.add_parser("export", help="Export to JSON")
    p_export.add_argument("--output", "-o", help="Output file")
    
    # import
    p_import = subparsers.add_parser("import", help="Import from JSON")
    p_import.add_argument("file", help="JSON file to import")
    
    # tags
    subparsers.add_parser("tags", help="List unique tags")
    
    args = parser.parse_args()
    
    # Run command
    if args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "count":
        cmd_count(args)
    elif args.cmd == "search":
        cmd_search(args)
    elif args.cmd == "store":
        cmd_store(args)
    elif args.cmd == "delete":
        cmd_delete(args)
    elif args.cmd == "export":
        cmd_export(args)
    elif args.cmd == "import":
        cmd_import(args)
    elif args.cmd == "tags":
        cmd_tags(args)

if __name__ == "__main__":
    main()
