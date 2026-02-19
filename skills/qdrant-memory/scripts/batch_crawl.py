#!/usr/bin/env python3
"""
Batch URL Crawler - Scrape multiple URLs to knowledge base
Usage: batch_crawl.py urls.txt --domain "Python" --path "Docs/Tutorials"
"""

import argparse
import sys
import json
import concurrent.futures
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scrape_to_kb import fetch_url, extract_text, chunk_text, get_embedding, compute_checksum, store_in_kb

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "knowledge_base"

def load_urls(url_source):
    """Load URLs from file or JSON"""
    if url_source.endswith('.json'):
        with open(url_source) as f:
            data = json.load(f)
            return [(item['url'], item.get('title'), item.get('subjects', [])) 
                    for item in data]
    else:
        with open(url_source) as f:
            urls = []
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Parse URL [title] [subjects]
                    parts = line.split(' ', 1)
                    url = parts[0]
                    title = None
                    subjects = []
                    if len(parts) > 1:
                        # Check for [Title] and #subject1,#subject2
                        rest = parts[1]
                        if '[' in rest and ']' in rest:
                            title_match = rest[rest.find('[')+1:rest.find(']')]
                            title = title_match
                            rest = rest[rest.find(']')+1:]
                        if '#' in rest:
                            subjects = [s.strip() for s in rest.split('#') if s.strip()]
                    urls.append((url, title, subjects))
            return urls

def scrape_single(url_data, domain, path, category, content_type):
    """Scrape a single URL"""
    url, title_override, subjects = url_data
    
    try:
        print(f"🔍 {url}")
        html = fetch_url(url)
        if not html:
            return {"url": url, "status": "failed", "error": "fetch"}
        
        title, text = extract_text(html)
        if title_override:
            title = title_override
        
        if len(text) < 200:
            return {"url": url, "status": "skipped", "reason": "too_short"}
        
        chunks = chunk_text(text)
        checksum = compute_checksum(text)
        
        stored = 0
        for i, chunk in enumerate(chunks):
            chunk_metadata = {
                "domain": domain,
                "path": f"{path}/chunk-{i+1}",
                "subjects": subjects,
                "category": category,
                "content_type": content_type,
                "title": f"{title} (part {i+1}/{len(chunks)})",
                "checksum": checksum,
                "source_url": url,
                "date_added": "2026-02-05",
                "chunk_index": i + 1,
                "total_chunks": len(chunks),
                "text_preview": chunk[:200] + "..." if len(chunk) > 200 else chunk
            }
            
            if store_in_kb(chunk, chunk_metadata):
                stored += 1
        
        return {
            "url": url,
            "status": "success",
            "chunks": len(chunks),
            "stored": stored,
            "title": title
        }
    except Exception as e:
        return {"url": url, "status": "error", "error": str(e)}

def main():
    parser = argparse.ArgumentParser(description="Batch scrape URLs to knowledge base")
    parser.add_argument("urls", help="File with URLs (.txt or .json)")
    parser.add_argument("--domain", required=True, help="Knowledge domain")
    parser.add_argument("--path", required=True, help="Hierarchical path")
    parser.add_argument("--category", default="reference", 
                       choices=["reference", "tutorial", "snippet", "troubleshooting", "concept"])
    parser.add_argument("--content-type", default="web_page")
    parser.add_argument("--workers", type=int, default=3, help="Concurrent workers (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Test without storing")
    
    args = parser.parse_args()
    
    urls = load_urls(args.urls)
    print(f"📋 Loaded {len(urls)} URLs")
    print(f"🏷️  Domain: {args.domain}")
    print(f"📂 Path: {args.path}")
    print(f"⚡ Workers: {args.workers}")
    
    if args.dry_run:
        print("\n🔍 DRY RUN - No storage\n")
        for url, title, subjects in urls:
            print(f"  Would scrape: {url}")
            if title:
                print(f"    Title: {title}")
            if subjects:
                print(f"    Subjects: {', '.join(subjects)}")
        return
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(scrape_single, url_data, args.domain, args.path, 
                          args.category, args.content_type): url_data
            for url_data in urls
        }
        
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            
            if result["status"] == "success":
                print(f"  ✓ {result['title'][:50]}... ({result['stored']}/{result['chunks']} chunks)")
            elif result["status"] == "skipped":
                print(f"  ⚠ Skipped: {result.get('reason')}")
            else:
                print(f"  ✗ Failed: {result.get('error', 'unknown')}")
    
    # Summary
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] in ["failed", "error"])
    skipped = sum(1 for r in results if r["status"] == "skipped")
    
    print(f"\n📊 Summary:")
    print(f"   ✓ Success: {success}")
    print(f"   ✗ Failed: {failed}")
    print(f"   ⚠ Skipped: {skipped}")

if __name__ == "__main__":
    main()
