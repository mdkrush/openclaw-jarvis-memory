#!/usr/bin/env python3
"""
JavaScript Scraper - Headless browser for JS-heavy sites
Uses Playwright to render dynamic content before scraping
Usage: js_scraper.py <url> --domain "React" --path "Docs/Hooks" --wait-for "#content"
"""

import argparse
import sys
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from scrape_to_kb import chunk_text, get_embedding, compute_checksum, store_in_kb

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "knowledge_base"

def scrape_js_site(url, wait_for=None, wait_time=2000, scroll=False, viewport=None):
    """Scrape JavaScript-rendered site using Playwright"""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        context_options = {}
        if viewport:
            context_options["viewport"] = {"width": viewport[0], "height": viewport[1]}
        
        context = browser.new_context(**context_options)
        page = context.new_page()
        
        # Set user agent
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        
        try:
            print(f"🌐 Loading {url}...")
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for specific element if requested
            if wait_for:
                print(f"⏳ Waiting for {wait_for}...")
                page.wait_for_selector(wait_for, timeout=10000)
            
            # Additional wait for any animations/final renders
            page.wait_for_timeout(wait_time)
            
            # Scroll to bottom if requested (for infinite scroll pages)
            if scroll:
                print("📜 Scrolling...")
                prev_height = 0
                while True:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(500)
                    new_height = page.evaluate("document.body.scrollHeight")
                    if new_height == prev_height:
                        break
                    prev_height = new_height
            
            # Get page data
            title = page.title()
            
            # Extract clean text
            text = page.evaluate("""() => {
                // Remove script/style/nav/header/footer
                const scripts = document.querySelectorAll('script, style, nav, header, footer, aside, .advertisement, .ads');
                scripts.forEach(el => el.remove());
                
                // Get main content if available, else body
                const main = document.querySelector('main, article, [role="main"], .content, .post-content, .entry-content');
                const content = main || document.body;
                
                return content.innerText;
            }""")
            
            # Get any JSON-LD structured data
            json_ld = page.evaluate("""() => {
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                const data = [];
                scripts.forEach(s => {
                    try {
                        data.push(JSON.parse(s.textContent));
                    } catch(e) {}
                });
                return data;
            }""")
            
            # Get meta description
            meta_desc = page.evaluate("""() => {
                const meta = document.querySelector('meta[name=\"description\"], meta[property=\"og:description\"]');
                return meta ? meta.content : '';
            }""")
            
            browser.close()
            
            return {
                "title": title,
                "text": text,
                "meta_description": meta_desc,
                "json_ld": json_ld,
                "url": page.url  # Final URL after redirects
            }
            
        except Exception as e:
            browser.close()
            raise e

def main():
    parser = argparse.ArgumentParser(description="Scrape JavaScript-heavy sites")
    parser.add_argument("url", help="URL to scrape")
    parser.add_argument("--domain", required=True, help="Knowledge domain")
    parser.add_argument("--path", required=True, help="Hierarchical path")
    parser.add_argument("--wait-for", help="CSS selector to wait for")
    parser.add_argument("--wait-time", type=int, default=2000, help="Wait time in ms after load")
    parser.add_argument("--scroll", action="store_true", help="Scroll to bottom (for infinite scroll)")
    parser.add_argument("--viewport", help="Viewport size (e.g., 1920x1080)")
    parser.add_argument("--category", default="reference")
    parser.add_argument("--content-type", default="web_page")
    parser.add_argument("--subjects", help="Comma-separated subjects")
    parser.add_argument("--title", help="Override title")
    
    args = parser.parse_args()
    
    viewport = None
    if args.viewport:
        w, h = args.viewport.split('x')
        viewport = (int(w), int(h))
    
    try:
        result = scrape_js_site(
            args.url, 
            wait_for=args.wait_for,
            wait_time=args.wait_time,
            scroll=args.scroll,
            viewport=viewport
        )
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    title = args.title or result["title"]
    text = result["text"]
    
    print(f"📄 Title: {title}")
    print(f"📝 Content: {len(text)} chars")
    
    if len(text) < 200:
        print("❌ Content too short", file=sys.stderr)
        sys.exit(1)
    
    # Add meta description if available
    if result["meta_description"]:
        text = f"Description: {result['meta_description']}\n\n{text}"
    
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
            "title": f"{title} (part {i+1}/{len(chunks)})",
            "checksum": checksum,
            "source_url": result["url"],
            "date_added": "2026-02-05",
            "chunk_index": i + 1,
            "total_chunks": len(chunks),
            "text_preview": chunk[:200] + "..." if len(chunk) > 200 else chunk,
            "scraper_type": "playwright_headless",
            "rendered": True
        }
        
        if store_in_kb(chunk, chunk_metadata):
            stored += 1
            print(f"   ✓ Chunk {i+1}")
    
    print(f"\n🎉 Stored {stored}/{len(chunks)} chunks")

if __name__ == "__main__":
    main()
