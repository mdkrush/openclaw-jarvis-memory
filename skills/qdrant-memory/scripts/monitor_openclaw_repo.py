#!/usr/bin/env python3
"""
Monitor OpenClaw GitHub repo for relevant updates
Only outputs/announces when there are significant changes affecting our setup.
Always exits with code 0 to prevent "exec failed" logs.
Usage: monitor_openclaw_repo.py [--json]
"""

import argparse
import sys
import json
import urllib.request
import re
import hashlib
from datetime import datetime

QDRANT_URL = "http://10.0.0.40:6333"
KB_COLLECTION = "knowledge_base"

# Keywords that indicate relevance to our setup
RELEVANT_KEYWORDS = [
    "ollama", "model", "embedding", "llm", "ai",
    "telegram", "webchat", "signal", "discord",
    "skill", "skills", "qdrant", "memory", "search",
    "whisper", "tts", "voice", "cron",
    "gateway", "agent", "session", "vector",
    "browser", "exec", "read", "edit", "write",
    "breaking", "deprecated", "removed", "changed",
    "fix", "bug", "patch", "security", "vulnerability"
]

HIGH_PRIORITY_AREAS = [
    "ollama", "telegram", "qdrant", "memory", "skills",
    "voice", "cron", "gateway", "browser"
]

def fetch_github_api(url):
    headers = {
        'User-Agent': 'OpenClaw-KB-Monitor',
        'Accept': 'application/vnd.github.v3+json'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        return None

def fetch_github_html(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            html = response.read().decode('utf-8', errors='ignore')
            text = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:5000]
    except:
        return None

def get_embedding(text):
    import json as jsonlib
    data = {"model": "nomic-embed-text", "input": text[:1000]}
    req = urllib.request.Request(
        "http://localhost:11434/api/embed",
        data=jsonlib.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = jsonlib.loads(response.read().decode())
            return result.get("embeddings", [None])[0]
    except:
        return None

def search_kb_by_path(path_prefix):
    url = f"{QDRANT_URL}/collections/{KB_COLLECTION}/points/scroll"
    data = {"limit": 100, "with_payload": True}
    req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            points = result.get("result", {}).get("points", [])
            return [p for p in points if p.get("payload", {}).get("path", "").startswith(path_prefix)]
    except:
        return []

def store_in_kb(text, metadata):
    import uuid
    embedding = get_embedding(text)
    if not embedding:
        return None
    metadata["checksum"] = f"sha256:{hashlib.sha256(text.encode()).hexdigest()[:16]}"
    metadata["date_scraped"] = datetime.now().isoformat()
    metadata["text_preview"] = text[:300] + "..." if len(text) > 300 else text
    point = {"id": str(uuid.uuid4()), "vector": embedding, "payload": metadata}
    url = f"{QDRANT_URL}/collections/{KB_COLLECTION}/points"
    req = urllib.request.Request(url, data=json.dumps({"points": [point]}).encode(),
                                  headers={"Content-Type": "application/json"}, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            return result.get("status") == "ok"
    except:
        return False

def delete_kb_entry(entry_id):
    url = f"{QDRANT_URL}/collections/{KB_COLLECTION}/points/delete"
    data = {"points": [entry_id]}
    req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            return result.get("status") == "ok"
    except:
        return False

def is_relevant_change(text):
    text_lower = text.lower()
    found_keywords = [kw for kw in RELEVANT_KEYWORDS if kw in text_lower]
    high_priority_found = [area for area in HIGH_PRIORITY_AREAS if area in text_lower]
    return {
        "relevant": len(found_keywords) > 0,
        "keywords": found_keywords,
        "high_priority": high_priority_found,
        "score": len(found_keywords) + (len(high_priority_found) * 2)
    }

def evaluate_significance(changes):
    total_score = sum(c["analysis"]["score"] for c in changes)
    high_priority_count = sum(len(c["analysis"]["high_priority"]) for c in changes)
    return {
        "significant": total_score >= 3 or high_priority_count > 0,
        "total_score": total_score,
        "high_priority_count": high_priority_count
    }

def format_summary(changes, significance):
    lines = ["📊 OpenClaw Repo Update", f"📅 {datetime.now().strftime('%Y-%m-%d')}", ""]
    by_section = {}
    for change in changes:
        section = change["section"]
        if section not in by_section:
            by_section[section] = []
        by_section[section].append(change)
    
    for section, items in by_section.items():
        lines.append(f"📁 {section}")
        for item in items[:3]:
            title = item["title"][:50] + "..." if len(item["title"]) > 50 else item["title"]
            lines.append(f"   • {title}")
            if item["analysis"]["high_priority"]:
                lines.append(f"     ⚠️  Affects: {', '.join(item['analysis']['high_priority'][:2])}")
        if len(items) > 3:
            lines.append(f"   ... and {len(items) - 3} more")
        lines.append("")
    return "\n".join(lines)

def scrape_all_sections():
    sections = []
    main_text = fetch_github_html("https://github.com/openclaw/openclaw")
    if main_text:
        sections.append({"section": "Main Repo", "title": "openclaw/openclaw README",
                         "url": "https://github.com/openclaw/openclaw", "content": main_text})
    
    releases = fetch_github_api("https://api.github.com/repos/openclaw/openclaw/releases?per_page=5")
    if releases:
        for release in releases:
            sections.append({"section": "Release", "title": release.get("name", release.get("tag_name", "Unknown")),
                             "url": release.get("html_url", ""), "content": release.get("body", "")[:2000],
                             "published": release.get("published_at", "")})
    
    issues = fetch_github_api("https://api.github.com/repos/openclaw/openclaw/issues?state=open&per_page=5")
    if issues:
        for issue in issues:
            if "pull_request" not in issue:
                sections.append({"section": "Issue", "title": issue.get("title", "Unknown"),
                                 "url": issue.get("html_url", ""), "content": issue.get("body", "")[:1500] if issue.get("body") else "No description",
                                 "labels": [l.get("name", "") for l in issue.get("labels", [])]})
    return sections

def check_and_update():
    sections = scrape_all_sections()
    if not sections:
        return None, "No data scraped"
    
    existing_entries = search_kb_by_path("OpenClaw/GitHub")
    existing_checksums = {e.get("payload", {}).get("checksum", ""): e for e in existing_entries}
    changes_detected = []
    
    for section in sections:
        content = section["content"]
        if not content:
            continue
        checksum = f"sha256:{hashlib.sha256(content.encode()).hexdigest()[:16]}"
        if checksum in existing_checksums:
            continue
        
        analysis = is_relevant_change(content + " " + section["title"])
        section["analysis"] = analysis
        section["checksum"] = checksum
        changes_detected.append(section)
        
        for old_checksum, old_entry in existing_checksums.items():
            if old_entry.get("payload", {}).get("title", "") == section["title"]:
                delete_kb_entry(old_entry.get("id"))
                break
        
        metadata = {
            "domain": "OpenClaw", "path": f"OpenClaw/GitHub/{section['section']}/{section['title'][:30]}",
            "subjects": ["openclaw", "github", section['section'].lower()], "category": "reference",
            "content_type": "web_page", "title": section["title"], "source_url": section["url"],
            "date_added": datetime.now().strftime("%Y-%m-%d")
        }
        store_in_kb(content, metadata)
    
    if changes_detected:
        significance = evaluate_significance(changes_detected)
        if significance["significant"]:
            return {"changes": changes_detected, "significance": significance,
                    "summary": format_summary(changes_detected, significance)}, None
        else:
            return None, "Changes not significant"
    return None, "No changes detected"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    
    result, reason = check_and_update()
    
    # Always output JSON for cron compatibility, even if empty
    if args.json:
        print(json.dumps(result if result else {}))
    elif result:
        print(result["summary"])
    # If no result, output nothing (silent)
    
    # Always exit 0 to prevent "exec failed" logs
    sys.exit(0)

if __name__ == "__main__":
    main()
