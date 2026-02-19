#!/usr/bin/env python3
"""
Initialize Qdrant collection for Projects
Usage: init_projects_collection.py [--recreate]
"""

import argparse
import sys
import urllib.request
import json

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "projects"

def make_request(url, data=None, method="GET"):
    """Make HTTP request with proper method"""
    req = urllib.request.Request(url, method=method)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    return req

def collection_exists():
    """Check if collection exists"""
    try:
        req = make_request(f"{QDRANT_URL}/collections/{COLLECTION_NAME}")
        with urllib.request.urlopen(req, timeout=5) as response:
            return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise
    except Exception as e:
        print(f"Error checking collection: {e}", file=sys.stderr)
        return False

def create_collection():
    """Create the projects collection using PUT"""
    config = {
        "vectors": {
            "size": 768,  # nomic-embed-text outputs 768 dimensions
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
        print(f"Error creating collection: {e}", file=sys.stderr)
        return False

def delete_collection():
    """Delete collection if exists"""
    req = make_request(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
        method="DELETE"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return True
    except Exception as e:
        print(f"Error deleting collection: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize Qdrant projects collection")
    parser.add_argument("--recreate", action="store_true", help="Delete and recreate collection")
    
    args = parser.parse_args()
    
    # Check if Qdrant is reachable
    try:
        req = make_request(f"{QDRANT_URL}/")
        with urllib.request.urlopen(req, timeout=3) as response:
            pass
    except Exception as e:
        print(f"❌ Cannot connect to Qdrant at {QDRANT_URL}: {e}", file=sys.stderr)
        sys.exit(1)
    
    print(f"✅ Connected to Qdrant at {QDRANT_URL}")
    
    exists = collection_exists()
    
    if exists and args.recreate:
        print(f"Deleting existing collection '{COLLECTION_NAME}'...")
        if delete_collection():
            print(f"✅ Deleted collection")
            exists = False
        else:
            print(f"❌ Failed to delete collection", file=sys.stderr)
            sys.exit(1)
    
    if not exists:
        print(f"Creating collection '{COLLECTION_NAME}'...")
        if create_collection():
            print(f"✅ Created collection '{COLLECTION_NAME}'")
            print(f"   Vector size: 768, Distance: Cosine")
        else:
            print(f"❌ Failed to create collection", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"✅ Collection '{COLLECTION_NAME}' already exists")
    
    print("\n🎉 Qdrant projects collection ready!")
