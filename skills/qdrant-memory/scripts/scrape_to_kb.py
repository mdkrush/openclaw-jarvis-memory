#!/usr/bin/env python3
"""
Scrape web content and store in knowledge_base collection
Usage: scrape_to_kb.py <url> <domain> <path> [--title "Title"] [--subjects "a,b,c"]
"""

import argparse
import sys
import re
import hashlib
import urllib.request
import urllib.error
from html import unescape

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "knowledge_base"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"

def fetch_url(url):
    """Fetch URL content"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}", file=sys.stderr)
        return None

def extract_text(html):
    """Extract clean text from HTML"""
    # Remove script and style tags
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Extract title
    title_match = re.search(r'<title[^>]*>([^<]*)</title>', html, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else "Untitled"
    title = unescape(title)
    
    # Remove nav/header/footer common patterns
    html = re.sub(r'<nav[^>]*>.*?</nav>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<header[^>]*>.*?</header>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<footer[^>]*>.*?</footer>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Convert common block elements to newlines
    html = re.sub(r'</(p|div|h[1-6]|li|tr)>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    
    # Remove all remaining tags
    text = re.sub(r'<[^>]+>', ' ', html)
    
    # Clean up whitespace
    text = unescape(text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = '\n'.join(line.strip() for line in text.split('\n'))
    text = '\n'.join(line for line in text.split('\n') if line)
    
    return title, text

def chunk_text(text, max_chars=2000, overlap=200):
    """Split text into overlapping chunks"""
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + max_chars
        
        # Try to break at sentence or paragraph
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind('\n\n', start, end)
            if para_break > start + 500:
                end = para_break
            else:
                # Look for sentence break
                sent_break = max(
                    text.rfind('. ', start, end),
                    text.rfind('? ', start, end),
                    text.rfind('! ', start, end)
                )
                if sent_break > start + 500:
                    end = sent_break + 1
        
        chunk = text[start:end].strip()
        if len(chunk) > 100:  # Skip tiny chunks
            chunks.append(chunk)
        
        start = end - overlap
        if start >= len(text):
            break
    
    return chunks

def get_embedding(text):
    """Generate embedding via Ollama"""
    import json
    data = {
        "model": "nomic-embed-text",
        "input": text
    }
    req = urllib.request.Request(
        OLLAMA_EMBED_URL,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode())
            return result.get("embeddings", [None])[0]
    except Exception as e:
        print(f"❌ Error generating embedding: {e}", file=sys.stderr)
        return None

def compute_checksum(text):
    """Compute SHA256 checksum"""
    return f"sha256:{hashlib.sha256(text.encode()).hexdigest()}"

def store_in_kb(text, metadata):
    """Store chunk in knowledge_base"""
    import json
    import uuid
    
    embedding = get_embedding(text)
    if not embedding:
        return False
    
    point = {
        "id": str(uuid.uuid4()),
        "vector": embedding,
        "payload": metadata
    }
    
    url = f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points"
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
        print(f"❌ Error storing: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Scrape URL to knowledge base")
    parser.add_argument("url", help="URL to scrape")
    parser.add_argument("domain", help="Knowledge domain (e.g., Python, OpenClaw)")
    parser.add_argument("path", help="Hierarchical path (e.g., OpenClaw/Docs/Overview)")
    parser.add_argument("--title", help="Override title")
    parser.add_argument("--subjects", help="Comma-separated subjects")
    parser.add_argument("--category", default="reference", help="Category: reference|tutorial|snippet|troubleshooting|concept")
    parser.add_argument("--content-type", default="web_page", help="Content type: web_page|code|markdown|pdf|note")
    
    args = parser.parse_args()
    
    print(f"🔍 Fetching {args.url}...")
    html = fetch_url(args.url)
    if not html:
        sys.exit(1)
    
    print("✂️  Extracting text...")
    title, text = extract_text(html)
    if args.title:
        title = args.title
    
    print(f"📄 Title: {title}")
    print(f"📝 Content length: {len(text)} chars")
    
    if len(text) < 200:
        print("❌ Content too short, skipping", file=sys.stderr)
        sys.exit(1)
    
    print("🧩 Chunking...")
    chunks = chunk_text(text)
    print(f"   {len(chunks)} chunks")
    
    subjects = [s.strip() for s in args.subjects.split(",")] if args.subjects else []
    checksum = compute_checksum(text)
    date_added = "2026-02-05"
    
    print("💾 Storing chunks...")
    stored = 0
    for i, chunk in enumerate(chunks):
        chunk_metadata = {
            "domain": args.domain,
            "path": f"{args.path}/chunk-{i+1}",
            "subjects": subjects,
            "category": args.category,
            "content_type": args.content_type,
            "title": f"{title} (part {i+1}/{len(chunks)})",
            "checksum": checksum,
            "source_url": args.url,
            "date_added": date_added,
            "chunk_index": i + 1,
            "total_chunks": len(chunks),
            "text_preview": chunk[:200] + "..." if len(chunk) > 200 else chunk
        }
        
        if store_in_kb(chunk, chunk_metadata):
            stored += 1
            print(f"   ✓ Chunk {i+1}/{len(chunks)}")
        else:
            print(f"   ✗ Chunk {i+1}/{len(chunks)} failed")
    
    print(f"\n🎉 Stored {stored}/{len(chunks)} chunks in knowledge_base")
    print(f"   Domain: {args.domain}")
    print(f"   Path: {args.path}")

if __name__ == "__main__":
    main()
