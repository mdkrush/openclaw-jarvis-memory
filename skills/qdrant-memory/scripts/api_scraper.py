#!/usr/bin/env python3
"""
API Scraper - REST API client with pagination support
Usage: api_scraper.py https://api.example.com/items --domain "API" --path "Endpoints/Items"
"""

import argparse
import sys
import json
import urllib.request
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from scrape_to_kb import chunk_text, get_embedding, compute_checksum, store_in_kb

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "knowledge_base"

class APIScraper:
    def __init__(self, base_url, headers=None, rate_limit=0):
        self.base_url = base_url
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json'
        }
        self.rate_limit = rate_limit  # seconds between requests
        
    def fetch(self, url, params=None):
        """Fetch JSON from API"""
        if params:
            import urllib.parse
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}" if '?' not in url else f"{url}&{query}"
        
        req = urllib.request.Request(url, headers=self.headers)
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            print(f"❌ HTTP {e.code}: {e.reason}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            return None
    
    def paginate(self, endpoint, page_param="page", size_param="limit", 
                 size=100, max_pages=None, data_key=None):
        """Fetch paginated results"""
        all_data = []
        page = 1
        
        while True:
            params = {page_param: page, size_param: size}
            url = f"{self.base_url}{endpoint}" if not endpoint.startswith('http') else endpoint
            
            print(f"📄 Fetching page {page}...")
            data = self.fetch(url, params)
            
            if not data:
                break
            
            # Extract items from response
            if data_key:
                items = data.get(data_key, [])
            elif isinstance(data, list):
                items = data
            else:
                # Try common keys
                for key in ['data', 'items', 'results', 'records', 'docs']:
                    if key in data:
                        items = data[key]
                        break
                else:
                    items = [data]  # Single item
            
            if not items:
                break
            
            all_data.extend(items)
            
            # Check for more pages
            if max_pages and page >= max_pages:
                print(f"   Reached max pages ({max_pages})")
                break
            
            # Check if we got less than requested (last page)
            if len(items) < size:
                break
            
            page += 1
            
            if self.rate_limit:
                import time
                time.sleep(self.rate_limit)
        
        return all_data
    
    def format_for_kb(self, items, format_template=None):
        """Format API items as text for knowledge base"""
        if not items:
            return ""
        
        parts = []
        
        for i, item in enumerate(items):
            if format_template:
                # Use custom template
                try:
                    text = format_template.format(**item, index=i+1)
                except KeyError:
                    text = json.dumps(item, indent=2)
            else:
                # Auto-format
                text = self._auto_format(item)
            
            parts.append(text)
        
        return "\n\n---\n\n".join(parts)
    
    def _auto_format(self, item):
        """Auto-format a JSON item as readable text"""
        if isinstance(item, str):
            return item
        
        if not isinstance(item, dict):
            return json.dumps(item, indent=2)
        
        parts = []
        
        # Title/Name first
        for key in ['name', 'title', 'id', 'key']:
            if key in item:
                parts.append(f"# {item[key]}")
                break
        
        # Description/summary
        for key in ['description', 'summary', 'content', 'body', 'text']:
            if key in item:
                parts.append(f"\n{item[key]}")
                break
        
        # Other fields
        skip = ['name', 'title', 'id', 'key', 'description', 'summary', 'content', 'body', 'text']
        for key, value in item.items():
            if key in skip:
                continue
            if value is None:
                continue
            if isinstance(value, (list, dict)):
                value = json.dumps(value, indent=2)
            parts.append(f"\n**{key}:** {value}")
        
        return "\n".join(parts)

def main():
    parser = argparse.ArgumentParser(description="Scrape REST API to knowledge base")
    parser.add_argument("url", help="API endpoint URL")
    parser.add_argument("--domain", required=True, help="Knowledge domain")
    parser.add_argument("--path", required=True, help="Hierarchical path")
    parser.add_argument("--paginate", action="store_true", help="Enable pagination")
    parser.add_argument("--page-param", default="page", help="Page parameter name")
    parser.add_argument("--size-param", default="limit", help="Page size parameter name")
    parser.add_argument("--size", type=int, default=100, help="Items per page")
    parser.add_argument("--max-pages", type=int, help="Max pages to fetch")
    parser.add_argument("--data-key", help="Key containing data array in response")
    parser.add_argument("--header", action='append', nargs=2, metavar=('KEY', 'VALUE'),
                       help="Custom headers (e.g., --header Authorization 'Bearer token')")
    parser.add_argument("--format", help="Python format string for item display")
    parser.add_argument("--category", default="reference")
    parser.add_argument("--content-type", default="api_data")
    parser.add_argument("--subjects", help="Comma-separated subjects")
    parser.add_argument("--title", help="Content title")
    parser.add_argument("--output", "-o", help="Save to JSON file instead of KB")
    parser.add_argument("--rate-limit", type=float, default=0.5, 
                       help="Seconds between requests (default: 0.5)")
    
    args = parser.parse_args()
    
    # Build headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/json'
    }
    if args.header:
        for key, value in args.header:
            headers[key] = value
    
    scraper = APIScraper(args.url, headers=headers, rate_limit=args.rate_limit)
    
    print(f"🔌 API: {args.url}")
    print(f"🏷️  Domain: {args.domain}")
    print(f"📂 Path: {args.path}")
    
    # Fetch data
    if args.paginate:
        print("📄 Pagination enabled\n")
        items = scraper.paginate(
            args.url,
            page_param=args.page_param,
            size_param=args.size_param,
            size=args.size,
            max_pages=args.max_pages,
            data_key=args.data_key
        )
    else:
        print("📄 Single request\n")
        data = scraper.fetch(args.url)
        if data_key := args.data_key:
            items = data.get(data_key, []) if data else []
        elif isinstance(data, list):
            items = data
        else:
            items = [data] if data else []
    
    if not items:
        print("❌ No data fetched", file=sys.stderr)
        sys.exit(1)
    
    print(f"✓ Fetched {len(items)} items")
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(items, f, indent=2)
        print(f"💾 Saved raw data to {args.output}")
        return
    
    # Format for KB
    text = scraper.format_for_kb(items, args.format)
    
    print(f"📝 Formatted: {len(text)} chars")
    
    if len(text) < 200:
        print("❌ Content too short", file=sys.stderr)
        sys.exit(1)
    
    chunks = chunk_text(text)
    print(f"🧩 Chunks: {len(chunks)}")
    
    subjects = [s.strip() for s in args.subjects.split(",")] if args.subjects else []
    checksum = compute_checksum(text)
    title = args.title or f"API Data from {args.url}"
    
    print("💾 Storing...")
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
            "date_added": datetime.now().strftime("%Y-%m-%d"),
            "chunk_index": i + 1,
            "total_chunks": len(chunks),
            "text_preview": chunk[:200] + "..." if len(chunk) > 200 else chunk,
            "scraper_type": "api_rest",
            "item_count": len(items),
            "api_endpoint": args.url
        }
        
        if store_in_kb(chunk, chunk_metadata):
            stored += 1
            print(f"   ✓ Chunk {i+1}")
    
    print(f"\n🎉 Stored {stored}/{len(chunks)} chunks")
    print(f"   Source: {args.url}")
    print(f"   Items: {len(items)}")

if __name__ == "__main__":
    main()
