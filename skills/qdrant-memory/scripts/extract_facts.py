#!/usr/bin/env python3
"""
Fact Extraction Script - Parse daily logs and extract atomic memories

This script parses memory/YYYY-MM-DD.md files and extracts individual facts
for storage in Qdrant as atomic memory units (Mem0-style), NOT whole files.

NOTE: Configured for COMPREHENSIVE capture (even minor facts) - user has
abundant storage resources. Thresholds are intentionally low to maximize
memory retention. Use --min-length flag to adjust filtering if needed.

Usage:
    extract_facts.py [--date 2026-02-15] [--dry-run] [--batch-size 50]
    extract_facts.py --backfill-all  # Process all missing dates

Features:
    - Parses markdown sections as individual facts
    - Generates embeddings per fact (not per file)
    - Stores with rich metadata (tags, importance, source)
    - Batch upload support
    - Duplicate detection
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

# Configuration
QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "kimi_memories"
OLLAMA_EMBED_URL = "http://localhost:11434/v1"
MEMORY_DIR = Path("/root/.openclaw/workspace/memory")
DEFAULT_BATCH_SIZE = 50


def get_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding using snowflake-arctic-embed2 via Ollama"""
    data = json.dumps({
        "model": "snowflake-arctic-embed2",
        "input": text[:8192]  # Limit to 8k chars
    }).encode()
    
    req = urllib.request.Request(
        f"{OLLAMA_EMBED_URL}/embeddings",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            return result["data"][0]["embedding"]
    except Exception as e:
        print(f"Error generating embedding: {e}", file=sys.stderr)
        return None


def batch_get_embeddings(texts: List[str]) -> List[Optional[List[float]]]:
    """Generate embeddings for multiple texts in batch"""
    if not texts:
        return []
    
    data = json.dumps({
        "model": "snowflake-arctic-embed2",
        "input": [t[:8192] for t in texts]
    }).encode()
    
    req = urllib.request.Request(
        f"{OLLAMA_EMBED_URL}/embeddings",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode())
            return [d["embedding"] for d in result["data"]]
    except Exception as e:
        print(f"Error generating batch embeddings: {e}", file=sys.stderr)
        return [None] * len(texts)


def parse_markdown_sections(content: str, date_str: str) -> List[Dict[str, Any]]:
    """
    Parse markdown content into atomic facts - COMPREHENSIVE CAPTURE.
    
    Extracts EVERYTHING:
    - ## Headers as fact categories
    - Individual bullet points as atomic facts
    - Paragraphs as standalone facts
    - Code blocks as facts
    - Table rows as facts
    - Lines with **bold** as critical rules
    - URLs/links as facts
    - Key-value pairs (Key: Value)
    """
    facts = []
    lines = content.split('\n')
    current_section = "General"
    current_section_content = []
    in_code_block = False
    code_block_content = []
    code_block_language = ""
    
    def flush_section_content():
        """Convert accumulated section content into facts"""
        nonlocal current_section_content
        if not current_section_content:
            return
        
        # Join lines and split into paragraphs
        full_text = '\n'.join(current_section_content)
        paragraphs = [p.strip() for p in full_text.split('\n\n') if p.strip()]
        
        for para in paragraphs:
            if len(para) < 5:  # Skip very short fragments
                continue
            
            # Split long paragraphs into sentence-level facts
            if len(para) > 300:
                sentences = [s.strip() for s in para.replace('. ', '.\n').split('\n') if s.strip()]
                for sentence in sentences:
                    if len(sentence) > 10:
                        facts.append({
                            "text": f"{current_section}: {sentence[:500]}",
                            "tags": extract_tags(sentence, date_str),
                            "importance": "high" if "**" in sentence else "medium",
                            "source_type": "inferred",
                            "category": current_section
                        })
            else:
                # Store whole paragraph as fact
                facts.append({
                    "text": f"{current_section}: {para[:500]}",
                    "tags": extract_tags(para, date_str),
                    "importance": "high" if "**" in para else "medium",
                    "source_type": "inferred",
                    "category": current_section
                })
        
        current_section_content = []
    
    def extract_tags(text: str, date_str: str) -> List[str]:
        """Extract relevant tags from text"""
        tags = ["atomic-fact", date_str]
        
        # Content-based tags
        text_lower = text.lower()
        tag_mappings = {
            "preference": "preferences",
            "config": "configuration",
            "hardware": "hardware",
            "security": "security",
            "youtube": "youtube",
            "video": "video",
            "workflow": "workflow",
            "rule": "rules",
            "critical": "critical",
            "decision": "decisions",
            "research": "research",
            "process": "process",
            "step": "steps",
        }
        
        for keyword, tag in tag_mappings.items():
            if keyword in text_lower:
                tags.append(tag)
        
        return tags
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Code blocks
        if line.startswith('```'):
            if in_code_block:
                # End of code block
                if code_block_content:
                    code_text = '\n'.join(code_block_content)
                    facts.append({
                        "text": f"{current_section} [Code: {code_block_language}]: {code_text[:800]}",
                        "tags": ["code-block", "atomic-fact", date_str, code_block_language],
                        "importance": "medium",
                        "source_type": "inferred",
                        "category": current_section
                    })
                code_block_content = []
                code_block_language = ""
                in_code_block = False
            else:
                # Start of code block
                flush_section_content()
                in_code_block = True
                code_block_language = line[3:].strip() or "text"
            continue
        
        if in_code_block:
            code_block_content.append(line)
            continue
        
        # Skip empty lines
        if not line:
            flush_section_content()
            continue
        
        # Section headers (##)
        if line.startswith('## '):
            flush_section_content()
            current_section = line[3:].strip()
            facts.append({
                "text": f"Section: {current_section}",
                "tags": ["section-header", "atomic-fact", date_str],
                "importance": "medium",
                "source_type": "inferred",
                "category": current_section
            })
            continue
        
        # Skip main title (# Title)
        if line.startswith('# ') and i == 0:
            continue
        
        # Bullet points (all levels)
        if line.startswith('- ') or line.startswith('* ') or line.startswith('+ '):
            flush_section_content()
            fact_text = line[2:].strip()
            if len(fact_text) > 3:
                facts.append({
                    "text": f"{current_section}: {fact_text[:500]}",
                    "tags": extract_tags(fact_text, date_str),
                    "importance": "high" if "**" in fact_text else "medium",
                    "source_type": "inferred",
                    "category": current_section
                })
            continue
        
        # Numbered lists
        if re.match(r'^\d+\.\s', line):
            flush_section_content()
            fact_text = re.sub(r'^\d+\.\s*', '', line)
            if len(fact_text) > 3:
                facts.append({
                    "text": f"{current_section}: {fact_text[:500]}",
                    "tags": extract_tags(fact_text, date_str),
                    "importance": "high" if "**" in fact_text else "medium",
                    "source_type": "inferred",
                    "category": current_section
                })
            continue
        
        # URLs / Links
        url_match = re.search(r'https?://[^\s<>"\')\]]+', line)
        if url_match and len(line) < 300:
            facts.append({
                "text": f"{current_section}: {line[:400]}",
                "tags": ["url", "link", "atomic-fact", date_str],
                "importance": "medium",
                "source_type": "inferred",
                "category": current_section
            })
            continue
        
        # Key-value pairs (Key: Value)
        if ':' in line and len(line) < 200 and not line.startswith('**'):
            key_part = line.split(':')[0].strip()
            if key_part and len(key_part) < 50 and not key_part.startswith('#'):
                facts.append({
                    "text": f"{current_section}: {line[:400]}",
                    "tags": extract_tags(line, date_str) + ["key-value"],
                    "importance": "medium",
                    "source_type": "inferred",
                    "category": current_section
                })
                continue
        
        # Bold text / critical rules
        if '**' in line:
            flush_section_content()
            facts.append({
                "text": f"{current_section}: {line[:500]}",
                "tags": ["critical-rule", "high-priority", date_str],
                "importance": "high",
                "source_type": "user",
                "category": current_section
            })
            continue
        
        # Table rows (| col1 | col2 |)
        if '|' in line and not line.startswith('#'):
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if cells and not all(c.replace('-', '').replace(':', '') == '' for c in cells):
                facts.append({
                    "text": f"{current_section} [Table]: {' | '.join(cells)[:400]}",
                    "tags": ["table-row", "atomic-fact", date_str],
                    "importance": "medium",
                    "source_type": "inferred",
                    "category": current_section
                })
            continue
        
        # Accumulate regular content
        if len(line) > 2:
            current_section_content.append(line)
    
    # Flush remaining content
    flush_section_content()
    
    return facts


def check_existing_facts(date_str: str) -> set:
    """Check which facts from this date are already stored"""
    try:
        scroll_data = json.dumps({
            "limit": 1000,
            "with_payload": True,
            "filter": {
                "must": [{"key": "tags", "match": {"value": date_str}}]
            }
        }).encode()
        
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
            data=scroll_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            points = result.get("result", {}).get("points", [])
            # Return set of text previews (first 100 chars) for comparison
            return {p["payload"]["text"][:100] for p in points if "text" in p["payload"]}
    except Exception as e:
        print(f"Warning: Could not check existing facts: {e}", file=sys.stderr)
        return set()


def upload_facts_batch(facts: List[Dict[str, Any]], batch_size: int = 50) -> Tuple[int, int]:
    """Upload facts to Qdrant in batches"""
    total = len(facts)
    uploaded = 0
    failed = 0
    
    for i in range(0, total, batch_size):
        batch = facts[i:i + batch_size]
        
        # Generate embeddings for this batch
        texts = [f["text"] for f in batch]
        embeddings = batch_get_embeddings(texts)
        
        # Prepare points
        points = []
        for fact, embedding in zip(batch, embeddings):
            if embedding is None:
                failed += 1
                continue
            
            point_id = str(uuid.uuid4())
            date_str = fact.get("date", datetime.now().strftime("%Y-%m-%d"))
            
            payload = {
                "text": fact["text"],
                "date": date_str,
                "tags": fact.get("tags", []),
                "importance": fact.get("importance", "medium"),
                "source": fact.get("source", "fact-extraction"),
                "source_type": fact.get("source_type", "inferred"),
                "category": fact.get("category", "general"),
                "confidence": fact.get("confidence", "high"),
                "verified": fact.get("verified", True),
                "created_at": datetime.now().isoformat(),
                "access_count": 0,
                "last_accessed": datetime.now().isoformat()
            }
            
            # NOTE: Memories never expire - user requested permanent retention
            # No expires_at field set = memories persist indefinitely
            
            points.append({
                "id": point_id,
                "vector": embedding,
                "payload": payload
            })
        
        if not points:
            continue
        
        # Upload batch
        upsert_data = {"points": points}
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points?wait=true",
            data=json.dumps(upsert_data).encode(),
            headers={"Content-Type": "application/json"},
            method="PUT"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode())
                if result.get("status") == "ok":
                    uploaded += len(points)
                    print(f"  ✅ Batch {i//batch_size + 1}: {len(points)} facts uploaded")
                else:
                    print(f"  ❌ Batch {i//batch_size + 1}: Failed")
                    failed += len(points)
        except Exception as e:
            print(f"  ❌ Batch {i//batch_size + 1}: {e}", file=sys.stderr)
            failed += len(points)
    
    return uploaded, failed


def process_single_date(date_str: str, dry_run: bool = False, batch_size: int = 50) -> Tuple[int, int]:
    """Process a single date's memory file"""
    file_path = MEMORY_DIR / f"{date_str}.md"
    
    if not file_path.exists():
        print(f"  ⚠️  File not found: {file_path}")
        return 0, 0
    
    print(f"Processing {date_str}...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Parse into atomic facts
    facts = parse_markdown_sections(content, date_str)
    
    if not facts:
        print(f"  ⚠️  No facts extracted from {date_str}")
        return 0, 0
    
    print(f"  📄 Extracted {len(facts)} atomic facts")
    
    # Check for existing (skip duplicates)
    existing = check_existing_facts(date_str)
    new_facts = [f for f in facts if f["text"][:100] not in existing]
    
    if existing:
        print(f"  ⏭️  Skipping {len(facts) - len(new_facts)} duplicates")
    
    if not new_facts:
        print(f"  ✅ All facts already stored for {date_str}")
        return 0, 0
    
    print(f"  📤 Uploading {len(new_facts)} new facts...")
    
    if dry_run:
        print(f"  [DRY RUN] Would upload {len(new_facts)} facts")
        for f in new_facts[:3]:  # Show first 3
            print(f"    - {f['text'][:80]}...")
        if len(new_facts) > 3:
            print(f"    ... and {len(new_facts) - 3} more")
        return len(new_facts), 0
    
    # Add date to each fact
    for f in new_facts:
        f["date"] = date_str
    
    uploaded, failed = upload_facts_batch(new_facts, batch_size)
    return uploaded, failed


def get_all_memory_dates() -> List[str]:
    """Get all memory file dates sorted"""
    if not MEMORY_DIR.exists():
        return []
    
    dates = []
    for f in MEMORY_DIR.glob("????-??-??.md"):
        dates.append(f.stem)
    
    dates.sort()
    return dates


def main():
    parser = argparse.ArgumentParser(
        description="Extract atomic facts from daily logs and store in Qdrant"
    )
    parser.add_argument("--date", help="Specific date to process (YYYY-MM-DD)")
    parser.add_argument("--backfill-all", action="store_true", 
                        help="Process all memory files")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be stored without uploading")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Batch size for uploads (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--force", action="store_true",
                        help="Re-process even if already stored")
    
    args = parser.parse_args()
    
    print(f"=== Fact Extraction ===")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Batch size: {args.batch_size}")
    print()
    
    if args.date:
        # Single date
        uploaded, failed = process_single_date(args.date, args.dry_run, args.batch_size)
        print(f"\n{'=' * 50}")
        print(f"Summary for {args.date}:")
        print(f"  Uploaded: {uploaded}")
        print(f"  Failed: {failed}")
    
    elif args.backfill_all:
        # All dates
        dates = get_all_memory_dates()
        print(f"Found {len(dates)} memory files to process")
        print()
        
        total_uploaded = 0
        total_failed = 0
        
        for date_str in dates:
            uploaded, failed = process_single_date(date_str, args.dry_run, args.batch_size)
            total_uploaded += uploaded
            total_failed += failed
            print()
        
        print(f"{'=' * 50}")
        print(f"Total Summary:")
        print(f"  Files processed: {len(dates)}")
        print(f"  Total uploaded: {total_uploaded}")
        print(f"  Total failed: {total_failed}")
    
    else:
        # Default to today
        today = datetime.now().strftime("%Y-%m-%d")
        uploaded, failed = process_single_date(today, args.dry_run, args.batch_size)
        print(f"\n{'=' * 50}")
        print(f"Summary for {today}:")
        print(f"  Uploaded: {uploaded}")
        print(f"  Failed: {failed}")
    
    print()
    print("✅ Fact extraction complete!")
    print("\nNext steps:")
    print("  - Search facts: python3 search_memories.py 'your query'")
    print("  - View by date: Check Qdrant with tag filter for date")


if __name__ == "__main__":
    main()
