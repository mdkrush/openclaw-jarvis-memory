#!/usr/bin/env python3
"""
Smart Parser - BeautifulSoup with CSS selectors for custom extraction
Usage: smart_parser.py <url> --selector "article .content" --domain "Blog" --path "Tech/AI"
"""

import argparse
import sys
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
import urllib.request

sys.path.insert(0, str(Path(__file__).parent))
from scrape_to_kb import chunk_text, get_embedding, compute_checksum, store_in_kb, fetch_url

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "knowledge_base"

def parse_with_selectors(html, selectors):
    """Extract content using CSS selectors"""
    soup = BeautifulSoup(html, 'lxml')
    
    # Default: get title
    title_tag = soup.find('title')
    title = title_tag.get_text().strip() if title_tag else "Untitled"
    
    results = {
        "title": title,
        "content": "",
        "sections": [],
        "metadata": {}
    }
    
    for name, selector in selectors.items():
        if name == "_content":
            # Main content selector
            elements = soup.select(selector)
            if elements:
                results["content"] = "\n\n".join(el.get_text(separator='\n', strip=True) for el in elements)
        elif name == "_title":
            # Title override selector
            el = soup.select_one(selector)
            if el:
                results["title"] = el.get_text(strip=True)
        elif name.startswith("_"):
            # Special selectors
            if name == "_code_blocks":
                # Extract code separately
                code_blocks = soup.select(selector)
                results["metadata"]["code_blocks"] = [
                    {"lang": el.get('class', [''])[0].replace('language-', '').replace('lang-', ''),
                     "code": el.get_text()}
                    for el in code_blocks
                ]
            elif name == "_links":
                links = soup.select(selector)
                results["metadata"]["links"] = [
                    {"text": el.get_text(strip=True), "href": el.get('href')}
                    for el in links if el.get('href')
                ]
        else:
            # Named section
            elements = soup.select(selector)
            if elements:
                section_text = "\n\n".join(el.get_text(separator='\n', strip=True) for el in elements)
                results["sections"].append({"name": name, "content": section_text})
    
    # If no content selector matched, try to auto-extract main content
    if not results["content"]:
        # Try common content selectors
        for sel in ['main', 'article', '[role="main"]', '.content', '.post', '.entry', '#content']:
            el = soup.select_one(sel)
            if el:
                # Remove nav/footer from content
                for unwanted in el.find_all(['nav', 'footer', 'aside', 'header']):
                    unwanted.decompose()
                results["content"] = el.get_text(separator='\n', strip=True)
                break
        
        # Fallback: body minus nav/header/footer
        if not results["content"]:
            body = soup.find('body')
            if body:
                for unwanted in body.find_all(['nav', 'header', 'footer', 'aside', 'script', 'style']):
                    unwanted.decompose()
                results["content"] = body.get_text(separator='\n', strip=True)
    
    return results

def format_extracted(data, include_sections=True):
    """Format extracted data into clean text"""
    parts = []
    
    # Title
    parts.append(f"# {data['title']}\n")
    
    # Content
    if data["content"]:
        parts.append(data["content"])
    
    # Sections
    if include_sections and data["sections"]:
        for section in data["sections"]:
            parts.append(f"\n## {section['name']}\n")
            parts.append(section["content"])
    
    # Metadata
    if data["metadata"].get("code_blocks"):
        parts.append("\n\n## Code Examples\n")
        for cb in data["metadata"]["code_blocks"]:
            lang = cb["lang"] or "text"
            parts.append(f"\n```{lang}\n{cb['code']}\n```\n")
    
    return "\n".join(parts)

def main():
    parser = argparse.ArgumentParser(description="Smart HTML parser with CSS selectors")
    parser.add_argument("url", help="URL to parse")
    parser.add_argument("--domain", required=True, help="Knowledge domain")
    parser.add_argument("--path", required=True, help="Hierarchical path")
    parser.add_argument("--selector", "-s", action='append', nargs=2, metavar=('NAME', 'CSS'),
                       help="CSS selector (e.g., -s content article -s title h1)")
    parser.add_argument("--content-only", action="store_true", help="Only extract main content")
    parser.add_argument("--title-selector", help="CSS selector for title")
    parser.add_argument("--remove", action='append', help="Selectors to remove")
    parser.add_argument("--category", default="reference")
    parser.add_argument("--content-type", default="web_page")
    parser.add_argument("--subjects", help="Comma-separated subjects")
    parser.add_argument("--title", help="Override title")
    parser.add_argument("--output", "-o", help="Save to file instead of KB")
    
    args = parser.parse_args()
    
    # Build selectors dict
    selectors = {}
    if args.selector:
        for name, css in args.selector:
            selectors[name] = css
    
    if args.content_only:
        selectors["_content"] = "main, article, [role='main'], .content, .post, .entry, #content, body"
    
    if args.title_selector:
        selectors["_title"] = args.title_selector
    
    if args.remove:
        selectors["_remove"] = ", ".join(args.remove)
    
    print(f"🔍 Fetching {args.url}...")
    html = fetch_url(args.url)
    if not html:
        sys.exit(1)
    
    print("🔧 Parsing...")
    data = parse_with_selectors(html, selectors)
    
    if args.title:
        data["title"] = args.title
    
    text = format_extracted(data)
    
    print(f"📄 Title: {data['title']}")
    print(f"📝 Content: {len(text)} chars")
    print(f"📊 Sections: {len(data['sections'])}")
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(text)
        print(f"💾 Saved to {args.output}")
        return
    
    if len(text) < 200:
        print("❌ Content too short", file=sys.stderr)
        sys.exit(1)
    
    chunks = chunk_text(text)
    print(f"🧩 Chunks: {len(chunks)}")
    
    subjects = [s.strip() for s in args.subjects.split(",")] if args.subjects else []
    checksum = compute_checksum(text)
    
    print("💾 Storing...")
    stored = 0
    for i, chunk in enumerate(chunks):
        chunk_metadata = {
            "domain": args.domain,
            "path": f"{args.path}/chunk-{i+1}",
            "subjects": subjects,
            "category": args.category,
            "content_type": args.content_type,
            "title": f"{data['title']} (part {i+1}/{len(chunks)})",
            "checksum": checksum,
            "source_url": args.url,
            "date_added": "2026-02-05",
            "chunk_index": i + 1,
            "total_chunks": len(chunks),
            "text_preview": chunk[:200] + "..." if len(chunk) > 200 else chunk,
            "scraper_type": "smart_parser_bs4",
            "extracted_sections": [s["name"] for s in data["sections"]]
        }
        
        if store_in_kb(chunk, chunk_metadata):
            stored += 1
            print(f"   ✓ Chunk {i+1}")
    
    print(f"\n🎉 Stored {stored}/{len(chunks)} chunks")

if __name__ == "__main__":
    main()
