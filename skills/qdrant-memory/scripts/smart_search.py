#!/usr/bin/env python3
"""
Hybrid search: knowledge_base first, then web search, store new findings.
Usage: smart_search.py "query" [--domain "Domain"] [--min-kb-score 0.5] [--store-new]
"""

import argparse
import sys
import json
import urllib.request
import urllib.parse
import re
from datetime import datetime

QDRANT_URL = "http://10.0.0.40:6333"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
SEARXNG_URL = "http://10.0.0.8:8888"
KB_COLLECTION = "knowledge_base"

def get_embedding(text):
    """Generate embedding via Ollama"""
    data = {
        "model": "nomic-embed-text",
        "input": text[:1000]  # Limit for speed
    }
    req = urllib.request.Request(
        OLLAMA_EMBED_URL,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            return result.get("embeddings", [None])[0]
    except Exception as e:
        print(f"⚠️  Embedding error: {e}", file=sys.stderr)
        return None

def search_knowledge_base(query, domain=None, limit=5, min_score=0.5):
    """Search knowledge base via vector similarity"""
    embedding = get_embedding(query)
    if not embedding:
        return []
    
    search_data = {
        "vector": embedding,
        "limit": limit,
        "with_payload": True
    }
    
    # Note: score_threshold filters aggressively; we filter client-side instead
    # to show users what scores were returned
    
    if domain:
        search_data["filter"] = {
            "must": [{"key": "domain", "match": {"value": domain}}]
        }
    
    url = f"{QDRANT_URL}/collections/{KB_COLLECTION}/points/search"
    req = urllib.request.Request(
        url,
        data=json.dumps(search_data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            results = result.get("result", [])
            # Filter by min_score client-side
            return [r for r in results if r.get("score", 0) >= min_score]
    except Exception as e:
        print(f"⚠️  KB search error: {e}", file=sys.stderr)
        return []

def web_search(query, limit=5):
    """Search via SearXNG"""
    encoded_query = urllib.parse.quote(query)
    url = f"{SEARXNG_URL}/?q={encoded_query}&format=json&safesearch=0"
    
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            return data.get("results", [])[:limit]
    except Exception as e:
        print(f"⚠️  Web search error: {e}", file=sys.stderr)
        return []

def fetch_and_extract(url):
    """Fetch URL and extract clean text"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            # Extract title
            title_match = re.search(r'<title[^>]*>([^<]*)</title>', html, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else "Untitled"
            
            # Clean HTML
            html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', html).strip()
            
            return title, text[:3000]  # Limit content
    except Exception as e:
        return None, None

def is_substantial(text, min_length=500):
    """Check if content is substantial enough to store"""
    return len(text) >= min_length

def is_unique_content(text, kb_results, similarity_threshold=0.8):
    """Check if content is unique compared to existing KB entries"""
    if not kb_results:
        return True
    
    # Simple check: if any KB result has very similar content, skip
    text_lower = text.lower()
    for result in kb_results:
        payload = result.get("payload", {})
        kb_text = payload.get("text_preview", "").lower()
        
        # Check for substantial overlap
        if kb_text and len(kb_text) > 100:
            # Simple word overlap check
            kb_words = set(kb_text.split())
            new_words = set(text_lower.split())
            if kb_words and new_words:
                overlap = len(kb_words & new_words) / len(kb_words)
                if overlap > similarity_threshold:
                    return False
    return True

def store_in_kb(text, metadata):
    """Store content in knowledge base"""
    import uuid
    import hashlib
    
    embedding = get_embedding(text[:1000])
    if not embedding:
        return False
    
    # Add metadata fields
    metadata["checksum"] = f"sha256:{hashlib.sha256(text.encode()).hexdigest()[:16]}"
    metadata["date_scraped"] = datetime.now().isoformat()
    metadata["text_preview"] = text[:300] + "..." if len(text) > 300 else text
    
    point = {
        "id": str(uuid.uuid4()),
        "vector": embedding,
        "payload": metadata
    }
    
    url = f"{QDRANT_URL}/collections/{KB_COLLECTION}/points"
    req = urllib.request.Request(
        url,
        data=json.dumps({"points": [point]}).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            return result.get("status") == "ok"
    except Exception as e:
        print(f"⚠️  Store error: {e}", file=sys.stderr)
        return False

def suggest_domain(query, title, content):
    """Suggest a domain based on query and content"""
    query_lower = query.lower()
    title_lower = title.lower()
    content_lower = content[:500].lower()
    
    # Keyword mapping
    domains = {
        "Python": ["python", "pip", "django", "flask", "asyncio"],
        "JavaScript": ["javascript", "js", "node", "react", "vue", "angular"],
        "Linux": ["linux", "ubuntu", "debian", "systemd", "bash", "shell"],
        "Networking": ["network", "dns", "tcp", "http", "ssl", "vpn"],
        "Docker": ["docker", "container", "kubernetes", "k8s"],
        "AI/ML": ["ai", "ml", "machine learning", "llm", "gpt", "model"],
        "OpenClaw": ["openclaw"],
        "Database": ["database", "sql", "postgres", "mysql", "redis"],
        "Security": ["security", "encryption", "auth", "oauth", "jwt"],
        "DevOps": ["devops", "ci/cd", "github actions", "jenkins"]
    }
    
    combined = query_lower + " " + title_lower + " " + content_lower
    
    for domain, keywords in domains.items():
        for kw in keywords:
            if kw in combined:
                return domain
    
    return "General"

def main():
    parser = argparse.ArgumentParser(description="Smart search: KB first, then web, store new")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--domain", help="Filter KB by domain")
    parser.add_argument("--min-kb-score", type=float, default=0.5, help="Minimum KB match score (default: 0.5)")
    parser.add_argument("--store-new", action="store_true", help="Automatically store new web findings")
    parser.add_argument("--web-limit", type=int, default=3, help="Number of web results to check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    results = {
        "query": args.query,
        "kb_results": [],
        "web_results": [],
        "stored_count": 0,
        "timestamp": datetime.now().isoformat()
    }
    
    # Step 1: Search knowledge base
    print(f"🔍 Searching knowledge base (min score: {args.min_kb_score})...")
    kb_results = search_knowledge_base(args.query, args.domain, limit=5, min_score=args.min_kb_score)
    results["kb_results"] = kb_results
    
    if kb_results:
        print(f"   ✓ Found {len(kb_results)} KB entries")
        for r in kb_results:
            payload = r.get("payload", {})
            score = r.get("score", 0)
            title = payload.get('title', 'Untitled')[:50]
            source = payload.get('source_url', 'N/A')[:40]
            print(f"     • {title}... (score: {score:.2f}) [{source}...]")
    else:
        print(f"   ✗ No KB matches above threshold ({args.min_kb_score})")
    
    # Step 2: Web search
    print(f"\n🌐 Searching web...")
    web_results = web_search(args.query, limit=args.web_limit)
    results["web_results"] = web_results
    
    if not web_results:
        print(f"   ✗ No web results")
        if args.json:
            print(json.dumps(results, indent=2))
        return
    
    print(f"   ✓ Found {len(web_results)} web results")
    
    # Step 3: Check and optionally store new findings
    new_stored = 0
    
    for web_result in web_results:
        url = web_result.get("url", "")
        title = web_result.get("title", "Untitled")
        snippet = web_result.get("content", "")
        
        print(f"\n📄 Checking: {title}")
        print(f"   URL: {url}")
        
        # Fetch full content
        fetched_title, content = fetch_and_extract(url)
        if not content:
            print(f"   ⚠️  Could not fetch content")
            continue
        
        title = fetched_title or title
        
        # Check if substantial
        if not is_substantial(content):
            print(f"   ⏭️  Content too short ({len(content)} chars), skipping")
            continue
        
        # Check if unique
        if not is_unique_content(content, kb_results):
            print(f"   ⏭️  Similar content already in KB")
            continue
        
        print(f"   ✓ New substantial content ({len(content)} chars)")
        
        # Auto-store or suggest
        if args.store_new:
            domain = suggest_domain(args.query, title, content)
            subjects = [s.strip() for s in args.query.lower().split() if len(s) > 3]
            
            metadata = {
                "domain": domain,
                "path": f"{domain}/Web/{re.sub(r'[^\w\s-]', '', title)[:30]}",
                "subjects": subjects,
                "category": "reference",
                "content_type": "web_page",
                "title": title,
                "source_url": url,
                "date_added": datetime.now().strftime("%Y-%m-%d")
            }
            
            if store_in_kb(content, metadata):
                print(f"   ✅ Stored in KB (domain: {domain})")
                new_stored += 1
            else:
                print(f"   ❌ Failed to store")
        else:
            print(f"   💡 Use --store-new to save this")
    
    results["stored_count"] = new_stored
    
    # Summary
    print(f"\n📊 Summary:")
    print(f"   KB results: {len(kb_results)}")
    print(f"   Web results checked: {len(web_results)}")
    print(f"   New items stored: {new_stored}")
    
    if args.json:
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
