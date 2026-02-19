#!/usr/bin/env python3
"""
Migrate Qdrant_Documents to 1024D vectors (snowflake-arctic-embed2) - BATCH VERSION
"""

import json
import sys
import urllib.request
import uuid
from datetime import datetime

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION = "Qdrant_Documents"
OLLAMA_URL = "http://localhost:11434/v1"
EXPORT_FILE = "/tmp/qd_export.json"
BATCH_SIZE = 50

def get_embeddings_batch(texts):
    """Generate embeddings in batch using snowflake-arctic-embed2"""
    # Truncate each text
    truncated = [t[:8000] for t in texts]
    data = json.dumps({
        "model": "snowflake-arctic-embed2",
        "input": truncated
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/embeddings",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            result = json.loads(r.read().decode())
            return [item["embedding"] for item in result["data"]]
    except Exception as e:
        print(f"Batch embed error: {e}", file=sys.stderr)
        return None

def make_request(url, data=None, method="GET"):
    req = urllib.request.Request(url, method=method)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    return req

def delete_collection():
    print(f"Deleting {COLLECTION}...")
    req = make_request(f"{QDRANT_URL}/collections/{COLLECTION}", method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"✅ Deleted")
    except Exception as e:
        print(f"Delete error: {e}")

def create_collection():
    print(f"Creating {COLLECTION} with 1024D vectors...")
    config = {
        "vectors": {
            "size": 1024,
            "distance": "Cosine"
        }
    }
    req = make_request(f"{QDRANT_URL}/collections/{COLLECTION}", data=config, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read().decode())
            if result.get("result") == True:
                print(f"✅ Created (1024D, Cosine)")
            else:
                print(f"❌ Failed: {result}")
                sys.exit(1)
    except Exception as e:
        print(f"❌ Create error: {e}")
        sys.exit(1)

def upsert_batch(points):
    """Upsert batch of points"""
    data = json.dumps({"points": points}).encode()
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true",
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode()).get("status") == "ok"
    except Exception as e:
        print(f"Upsert error: {e}", file=sys.stderr)
        return False

# Load exported docs
print(f"Loading {EXPORT_FILE}...")
with open(EXPORT_FILE, 'r') as f:
    docs = json.load(f)
print(f"Loaded {len(docs)} documents\n")

# Delete and recreate
delete_collection()
create_collection()
print()

# Process in batches
print(f"Re-embedding with snowflake-arctic-embed2 (batch={BATCH_SIZE})...\n")
success = 0
failed = 0
total_batches = (len(docs) + BATCH_SIZE - 1) // BATCH_SIZE

for batch_num in range(total_batches):
    start = batch_num * BATCH_SIZE
    end = min(start + BATCH_SIZE, len(docs))
    batch_docs = docs[start:end]
    
    print(f"Batch {batch_num + 1}/{total_batches} ({start}-{end})...", end=" ", flush=True)
    
    # Get texts for embedding
    texts = [d.get("payload", {}).get("text", "") for d in batch_docs]
    
    # Get embeddings
    embeddings = get_embeddings_batch(texts)
    if not embeddings:
        print(f"❌ embed failed")
        failed += len(batch_docs)
        continue
    
    # Build points
    points = []
    for doc, emb in zip(batch_docs, embeddings):
        points.append({
            "id": doc.get("id", str(uuid.uuid4())),
            "vector": emb,
            "payload": doc.get("payload", {})
        })
    
    # Upsert
    if upsert_batch(points):
        success += len(batch_docs)
        print(f"✅")
    else:
        failed += len(batch_docs)
        print(f"❌")

print()
print("=" * 50)
print(f"MIGRATION COMPLETE")
print(f"  Success: {success}")
print(f"  Failed: {failed}")
print(f"  Total: {len(docs)}")
print("=" * 50)

# Verify
req = make_request(f"{QDRANT_URL}/collections/{COLLECTION}")
with urllib.request.urlopen(req, timeout=5) as r:
    info = json.loads(r.read().decode())["result"]
    print(f"\n📚 {COLLECTION}")
    print(f"   Points: {info['points_count']:,}")
    print(f"   Vector size: {info['config']['params']['vectors']['size']}")
    print(f"   Distance: {info['config']['params']['vectors']['distance']}")
