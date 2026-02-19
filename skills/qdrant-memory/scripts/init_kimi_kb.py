#!/usr/bin/env python3
"""
Initialize kimi_kb collection (Knowledge Base)
Vector size: 1024 (snowflake-arctic-embed2)

Usage: init_kimi_kb.py [--recreate]
"""

import argparse
import sys
import urllib.request
import json

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "kimi_kb"
VECTOR_SIZE = 1024

def make_request(url, data=None, method="GET"):
    req = urllib.request.Request(url, method=method)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    return req

def collection_exists():
    try:
        req = make_request(f"{QDRANT_URL}/collections/{COLLECTION_NAME}")
        with urllib.request.urlopen(req, timeout=5) as response:
            return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise
    except Exception:
        return False

def get_info():
    try:
        req = make_request(f"{QDRANT_URL}/collections/{COLLECTION_NAME}")
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode())
    except Exception:
        return None

def create_collection():
    config = {
        "vectors": {
            "size": VECTOR_SIZE,
            "distance": "Cosine"
        }
    }
    req = make_request(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
        data=config,
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            return result.get("result") == True
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return False

def delete_collection():
    req = make_request(f"{QDRANT_URL}/collections/{COLLECTION_NAME}", method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode()).get("status") == "ok"
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize kimi_kb collection")
    parser.add_argument("--recreate", action="store_true", help="Delete and recreate")
    args = parser.parse_args()
    
    try:
        req = make_request(f"{QDRANT_URL}/")
        with urllib.request.urlopen(req, timeout=3) as response:
            pass
    except Exception as e:
        print(f"❌ Cannot connect to Qdrant: {e}", file=sys.stderr)
        sys.exit(1)
    
    print(f"✅ Qdrant: {QDRANT_URL}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Vector size: {VECTOR_SIZE} (snowflake-arctic-embed2)\n")
    
    exists = collection_exists()
    
    if exists:
        if args.recreate:
            print(f"Deleting existing...")
            delete_collection()
            exists = False
        else:
            info = get_info()
            if info:
                size = info.get("result", {}).get("vectors_config", {}).get("params", {}).get("vectors", {}).get("size", "?")
                points = info.get("result", {}).get("points_count", 0)
                print(f"⚠️ Already exists (vector size: {size}, points: {points})")
                sys.exit(0)
    
    if not exists:
        if create_collection():
            print(f"✅ Created {COLLECTION_NAME}")
            print(f"   Vector size: {VECTOR_SIZE}, Distance: Cosine")
        else:
            print(f"❌ Failed", file=sys.stderr)
            sys.exit(1)
