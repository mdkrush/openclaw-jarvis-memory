#!/usr/bin/env python3
"""
Hybrid search: Search both file-based memory and Qdrant vectors
Usage: hybrid_search.py "Query text" [--file-limit 3] [--vector-limit 3]
"""

import argparse
import json
import os
import subprocess
import sys
import re
from datetime import datetime, timedelta

WORKSPACE = "/root/.openclaw/workspace"
MEMORY_DIR = f"{WORKSPACE}/memory"

def search_files(query, limit=3):
    """Search recent memory files for keyword matches"""
    results = []
    
    # Get recent memory files (last 30 days)
    files = []
    today = datetime.now()
    for i in range(30):
        date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        filepath = f"{MEMORY_DIR}/{date_str}.md"
        if os.path.exists(filepath):
            files.append((date_str, filepath))
    
    # Simple keyword search
    query_lower = query.lower()
    keywords = set(query_lower.split())
    
    for date_str, filepath in files[:7]:  # Check last 7 days max
        try:
            with open(filepath, 'r') as f:
                content = f.read()
                
            # Find sections that match
            lines = content.split('\n')
            for i, line in enumerate(lines):
                line_lower = line.lower()
                if any(kw in line_lower for kw in keywords):
                    # Get context (3 lines before and after)
                    start = max(0, i - 3)
                    end = min(len(lines), i + 4)
                    context = '\n'.join(lines[start:end])
                    
                    # Simple relevance score based on keyword matches
                    score = sum(1 for kw in keywords if kw in line_lower) / len(keywords)
                    
                    results.append({
                        "source": f"file:{filepath}",
                        "date": date_str,
                        "score": score,
                        "text": context.strip(),
                        "type": "file"
                    })
                    
                    if len(results) >= limit * 2:  # Get more then dedupe
                        break
                        
        except Exception as e:
            continue
    
    # Sort by score and return top N
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]

def search_qdrant(query, limit=3):
    """Search Qdrant using the search_memories script"""
    try:
        script_path = f"{WORKSPACE}/skills/qdrant-memory/scripts/search_memories.py"
        result = subprocess.run(
            ["python3", script_path, query, "--limit", str(limit), "--json"],
            capture_output=True, text=True, timeout=60
        )
        
        if result.returncode == 0:
            memories = json.loads(result.stdout)
            for m in memories:
                m["type"] = "vector"
                m["source"] = "qdrant"
            return memories
    except Exception as e:
        print(f"Qdrant search failed (falling back to files only): {e}", file=sys.stderr)
    
    return []

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hybrid memory search")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--file-limit", type=int, default=3, help="Max file results")
    parser.add_argument("--vector-limit", type=int, default=3, help="Max vector results")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    print(f"Searching for: '{args.query}'\n", file=sys.stderr)
    
    # Search both sources
    file_results = search_files(args.query, args.file_limit)
    vector_results = search_qdrant(args.query, args.vector_limit)
    
    # Combine results
    all_results = file_results + vector_results
    
    if not all_results:
        print("No memories found matching your query.")
        sys.exit(0)
    
    if args.json:
        print(json.dumps(all_results, indent=2))
    else:
        print(f"📁 File-based results ({len(file_results)}):")
        print("-" * 50)
        for r in file_results:
            print(f"[{r['date']}] Score: {r['score']:.2f}")
            print(r['text'][:300])
            if len(r['text']) > 300:
                print("...")
            print()
        
        print(f"\n🔍 Vector (Qdrant) results ({len(vector_results)}):")
        print("-" * 50)
        for r in vector_results:
            print(f"[{r.get('date', 'unknown')}] Score: {r.get('score', 0):.3f} [{r.get('importance', 'medium')}]")
            text = r.get('text', '')
            print(text[:300])
            if len(text) > 300:
                print("...")
            if r.get('tags'):
                print(f"Tags: {', '.join(r['tags'])}")
            print()
