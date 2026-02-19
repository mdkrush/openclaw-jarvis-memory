#!/usr/bin/env python3
"""
Review knowledge base for outdated entries
Usage: kb_review.py [--days 180] [--domains "Domain1,Domain2"] [--dry-run]
"""

import argparse
import sys
import json
import urllib.request
from datetime import datetime, timedelta

QDRANT_URL = "http://10.0.0.40:6333"
KB_COLLECTION = "knowledge_base"

# Domains where freshness matters (tech changes fast)
FAST_MOVING_DOMAINS = ["AI/ML", "Python", "JavaScript", "Docker", "OpenClaw", "DevOps"]

def make_request(url, data=None, method="GET"):
    """Make HTTP request"""
    req = urllib.request.Request(url, method=method)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    return req

def get_all_entries(limit=1000):
    """Get all entries from knowledge base"""
    url = f"{QDRANT_URL}/collections/{KB_COLLECTION}/points/scroll"
    
    data = {
        "limit": limit,
        "with_payload": True
    }
    
    req = make_request(url, data, "POST")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            return result.get("result", {}).get("points", [])
    except Exception as e:
        print(f"❌ Error fetching entries: {e}", file=sys.stderr)
        return []

def parse_date(date_str):
    """Parse date string to datetime"""
    if not date_str:
        return None
    
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.split('.')[0], fmt)
        except:
            continue
    
    return None

def is_outdated(entry, threshold_days, fast_moving_multiplier=0.5):
    """Check if entry is outdated"""
    payload = entry.get("payload", {})
    
    # Check date_scraped first, then date_added
    date_str = payload.get("date_scraped") or payload.get("date_added")
    entry_date = parse_date(date_str)
    
    if not entry_date:
        return False, None  # No date, can't determine
    
    domain = payload.get("domain", "")
    
    # Fast-moving domains get shorter threshold
    if domain in FAST_MOVING_DOMAINS:
        effective_threshold = int(threshold_days * fast_moving_multiplier)
    else:
        effective_threshold = threshold_days
    
    age = datetime.now() - entry_date
    is_old = age.days > effective_threshold
    
    return is_old, {
        "age_days": age.days,
        "threshold": effective_threshold,
        "domain": domain,
        "date": date_str
    }

def delete_entry(entry_id):
    """Delete entry from knowledge base"""
    url = f"{QDRANT_URL}/collections/{KB_COLLECTION}/points/delete"
    data = {"points": [entry_id]}
    
    req = make_request(url, data, "POST")
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            return result.get("status") == "ok"
    except Exception as e:
        print(f"❌ Error deleting: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Review knowledge base for outdated entries")
    parser.add_argument("--days", type=int, default=180, help="Age threshold in days")
    parser.add_argument("--domains", help="Comma-separated domains to check (default: all)")
    parser.add_argument("--fast-moving-only", action="store_true", help="Only check fast-moving domains")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    parser.add_argument("--delete", action="store_true", help="Actually delete outdated entries")
    
    args = parser.parse_args()
    
    print(f"🔍 Fetching knowledge base entries...")
    entries = get_all_entries()
    
    if not entries:
        print("❌ No entries found")
        return
    
    print(f"   Total entries: {len(entries)}")
    
    # Filter by domain if specified
    if args.domains:
        target_domains = [d.strip() for d in args.domains.split(",")]
        entries = [e for e in entries if e.get("payload", {}).get("domain") in target_domains]
        print(f"   Filtered to domains: {target_domains}")
    elif args.fast_moving_only:
        entries = [e for e in entries if e.get("payload", {}).get("domain") in FAST_MOVING_DOMAINS]
        print(f"   Filtered to fast-moving domains: {FAST_MOVING_DOMAINS}")
    
    # Check for outdated entries
    outdated = []
    for entry in entries:
        is_old, info = is_outdated(entry, args.days)
        if is_old:
            outdated.append({
                "entry": entry,
                "info": info
            })
    
    if not outdated:
        print(f"\n✅ No outdated entries found!")
        return
    
    print(f"\n⚠️  Found {len(outdated)} outdated entries:")
    print(f"   (Threshold: {args.days} days, fast-moving: {int(args.days * 0.5)} days)")
    
    for item in outdated:
        entry = item["entry"]
        info = item["info"]
        payload = entry.get("payload", {})
        
        print(f"\n   📄 {payload.get('title', 'Untitled')}")
        print(f"      Domain: {info['domain']} | Age: {info['age_days']} days | Threshold: {info['threshold']} days")
        print(f"      Date: {info['date']}")
        print(f"      Path: {payload.get('path', 'N/A')}")
        
        if args.delete and not args.dry_run:
            if delete_entry(entry.get("id")):
                print(f"      ✅ Deleted")
            else:
                print(f"      ❌ Failed to delete")
        elif args.dry_run:
            print(f"      [Would delete in non-dry-run mode]")
    
    # Summary
    print(f"\n📊 Summary:")
    print(f"   Total checked: {len(entries)}")
    print(f"   Outdated: {len(outdated)}")
    
    if args.dry_run:
        print(f"\n💡 Use --delete to remove these entries")
    elif not args.delete:
        print(f"\n💡 Use --dry-run to preview, --delete to remove")

if __name__ == "__main__":
    main()
